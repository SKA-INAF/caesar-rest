##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import signal
import sys
import json
import time
import datetime
import logging
import numpy as np

try:
	FileNotFoundError  # python3
except NameError:
	FileNotFoundError = IOError # python2

try:
	from urllib.request import urlopen
except ImportError:
	from urllib2 import urlopen

# Import flask modules
from flask import current_app, Blueprint, render_template, request, redirect, url_for, flash, g
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
from werkzeug.utils import secure_filename

# Import celery modules
from celery import states
from celery.task.control import revoke

# Import Celery app
from caesar_rest.app import celery as celery_app
from caesar_rest import workers
from caesar_rest.workers import background_task
from caesar_rest import oidc
from caesar_rest import utils
from caesar_rest.decorators import custom_require_login
from caesar_rest import mongo
from caesar_rest import jobmgr_kube

# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINTS
##############################
job_bp = Blueprint('job', __name__,url_prefix='/caesar/api/v1.0')
job_status_bp = Blueprint('job_status', __name__,url_prefix='/caesar/api/v1.0')
job_output_bp = Blueprint('job_output', __name__,url_prefix='/caesar/api/v1.0')
job_cancel_bp = Blueprint('job_cancel', __name__,url_prefix='/caesar/api/v1.0')


#=================================
#===      JOB SUBMIT 
#=================================
@job_bp.route('/job', methods=['POST'])
@custom_require_login
def submit_job():
	""" Submit a job asyncronously """
	
	# - Init response
	res= {}
	res['status']= ''
	res['state']= ''
	res['app']= ''
	res['job_id']= ''
	res['submit_date']= ''

	# - Get aai info
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		email= g.oidc_token_info['email']
		username= utils.sanitize_username(email)

	# - Get mongo info
	mongo_dbhost= current_app.config['MONGO_HOST']
	mongo_dbport= current_app.config['MONGO_PORT']
	mongo_dbname= current_app.config['MONGO_DBNAME']

	# - Get other options
	job_scheduler= current_app.config['JOB_SCHEDULER']
	

	# - Get request data
	req_data = request.get_json(silent=True)
	if not req_data:
		logger.error("Invalid request data!")
		res['state']= 'ABORTED'
		res['status']= 'Invalid request data!'
		return make_response(jsonify(res),400)
	logger.info("Received job data %s " % str(req_data))

	app_name = req_data['app']
	job_inputs = req_data['job_inputs']
	if not app_name:
		logger.error("No app name given!")
		res['state']= 'ABORTED'
		res['status']= 'No app name found in request!'
		return make_response(jsonify(res),400)

	res['app']= app_name

	if not job_inputs:
		logger.error("No job inputs given!")	
		res['state']= 'ABORTED'	
		res['status']= 'No job inputs name found in request!'
		return make_response(jsonify(res),400)

	# - Check if valid app given
	#supported_app= app_name in current_app.config['APP_NAMES']
	#if not supported_app:
	#	logger.warn("App %s not supported..." % app_name)
	#	res['status']= 'App ' + app_name + ' is unknown or not yet supported!'
	#	return make_response(jsonify(res),400)

	# - Validate job inputs
	(cmd,cmd_arg_list,val_status)= current_app.config['jobcfg'].validate(app_name,job_inputs)
	if cmd is None or cmd_arg_list is None: 
		logger.warn("Job input validation failed!")
		res['state']= 'ABORTED'	
		res['status']= val_status
		return make_response(jsonify(res),400)

	
	# - Convert cmd arg list to string
	cmd_args= ''
	if cmd_arg_list:
		cmd_args= ' '.join(cmd_arg_list)

	# - Set job top directory
	job_top_dir= current_app.config['JOB_DIR'] + '/' + username

	# - Submit task async	
	#logger.info("Submitting job %s async (cmd=%s, args=%s) ..." % (app_name,cmd,cmd_args))
	#now = datetime.datetime.now()
	#submit_date= now.isoformat()
	#job_top_dir= current_app.config['JOB_DIR'] + '/' + username
	#job_monitoring_period= current_app.config['JOB_MONITORING_PERIOD']

	#task = background_task.apply_async(
	#	[app_name, cmd, cmd_args, job_top_dir, username, mongo_dbhost, mongo_dbport, mongo_dbname, job_monitoring_period],
	#	queue= app_name # set queue name to app name
	#)
	#job_id= task.id
	#logger.info("Submitted job with id=%s ..." % job_id)

	# - Submit task
	submit_res= {}
	if job_scheduler=='celery':
		submit_res= submit_job_celery(app_name, cmd, cmd_args, job_top_dir, username, mongo_dbhost, mongo_dbport, mongo_dbname)
	
	elif job_scheduler=='kubernetes':
		submit_res= submit_job_kubernetes(app_name, cmd_args, job_top_dir)

	elif job_scheduler=='slurm':
		submit_res= submit_job_slurm()

	if submit_res is None:
		logger.warn("Failed to submit job to scheduler %s!" % job_scheduler)
		res['state']= 'ABORTED'
		res['status']= 'Job failed to be submitted!'
		return make_response(jsonify(res),500)

	submit_date= submit_res['submit_date']

	# - Register task id in mongo
	logger.info("Creating job object for task %s ..." % job_id)
	job_obj= {
		"job_id": job_id,
		"submit_date": submit_date,
		"app": app_name,	
		"job_inputs": job_inputs,
		"metadata": '', # FIX ME
		"tag": '', # FIX ME
		"state": 'PENDING',
		"status": 'Job submitted',
		"pid": '',
		"elapsed_time": '0',
		"exit_code": -1
	}

	collection_name= username + '.jobs'

	try:
		logger.info("Creating or retrieving job collection for user %s ..." % username)
		job_collection= mongo.db[collection_name]

		logger.info("Adding job obj to collection ...")
		item_id= job_collection.insert(job_obj)
		
	except Exception as e:
		logger.warn("Failed to create and register job in DB (err=%s)!" % str(e))
		flash('Job submitted but failed to be registered in DB!')
		logger.warn("Job %s submitted but failed to be registered in DB!" % job_id)
		res['state']= 'PENDING'
		res['status']= 'WARN: Job submitted but failed to be registered in DB!'
		return make_response(jsonify(res),500)


	# - Fill response
	res['job_id']= job_id
	res['submit_date']= submit_date
	res['app']= app_name
	res['job_inputs']= job_inputs
	res['state']= 'PENDING'
	res['status']= 'Job submitted and registered with success'
	
	return make_response(jsonify(res),202)


#=================================
#===    SUBMIT JOB CELERY
#=================================
def submit_job_celery(app_name, cmd, cmd_args, job_top_dir, username, mongo_dbhost, mongo_dbport, mongo_dbname):
	""" Submit job to celery scheduler """

	# - Set task options
	now = datetime.datetime.now()
	submit_date= now.isoformat()
	job_monitoring_period= current_app.config['JOB_MONITORING_PERIOD']

	# - Submit task to queue
	logger.info("Submitting job %s async (cmd=%s, args=%s) ..." % (app_name,cmd,cmd_args))
	task = background_task.apply_async(
		[app_name, cmd, cmd_args, job_top_dir, username, mongo_dbhost, mongo_dbport, mongo_dbname, job_monitoring_period],
		queue= app_name # set queue name to app name
	)
	job_id= task.id
	logger.info("Submitted job with id=%s ..." % job_id)

	res= {
		"job_id": job_id,
		"submit_date": submit_date,
		"state": "PENDING",
		"status": "Job submitted to queue"
	}

	return res

#=================================
#===    SUBMIT JOB KUBERNETES
#=================================
def submit_job_kubernetes(app_name, cmd_args, job_top_dir):
	""" Submit job to Kubernetes scheduler """

	# - Init response
	res= {}

	# - Get app config options
	image= current_app.config['CAESAR_JOB_IMAGE']
	mount_rclone_vol= current_app.config['MOUNT_RCLONE_VOLUME']
	mount_vol_path= current_app.config['MOUNT_VOLUME_PATH']
	rclone_storage_name= current_app.config['RCLONE_REMOTE_STORAGE']
	rclone_storage_path= current_app.config['RCLONE_REMOTE_STORAGE_PATH']
	rclone_secret_name= current_app.config['RCLONE_SECRET_NAME']

	# - Generate job id
	job_id= utils.get_uuid()
	
	# - Create job object
	if app_name=="sfinder":
		if mount_rclone_vol:
			job= jobmgr_kube.create_caesar_rclone_job(
				job_args=cmd_args,
				job_name=job_id, 
				image=image, 
				rclone_storage_name=rclone_storage_name, 
				rclone_secret_name=rclone_secret_name, 
				rclone_storage_path=rclone_storage_path, 
				rclone_mount_path=mount_vol_path
			)
		else:
			logger.warn("Unsupported job type required!")
			return None
	else:
		logger.warn("Unknown/unsupported app %s!" % app_name)
		return None

	if job is None:
		logger.warn("Failed to create Kube job object!")
		return None

	# - Create job top dir
	job_dir_name= 'job_' + job_id
	job_dir= os.path.join(job_top_dir,job_dir_name)

	logger.info("Creating job dir %s (top dir=%s) ..." % (job_dir,job_top_dir))
	try:
		os.makedirs(job_dir)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			errmsg= "Failed to create job directory " + job_dir + "!" 
			logger.error(errmsg)
			return None

	# - Submit job
	now = datetime.datetime.now()
	submit_date= now.isoformat()
	submit_job= jobmgr_kube.submit_job(job)
	if submit_job is None:
		logger.warn("Failed to submit job %d to Kubernetes cluster!" % job_id)
		return None

	logger.info("Submitted job with id=%s ..." % job_id)

	res= {
		"job_id": job_id,
		"submit_date": submit_date,
		"state": "PENDING",
		"status": "Job submitted to Kubernetes scheduler"
	}

	return res

#=================================
#===    SUBMIT JOB SLURM
#=================================
def submit_job_slurm():
	""" Submit job to Slurm scheduler """

	# ...
	# ...

#=================================
#===      JOB IDs 
#=================================
@job_bp.route('/jobs', methods=['GET'])
@custom_require_login
def get_job_ids():
	""" Retrieve all job ids per user """

	# - Get aai info
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		email= g.oidc_token_info['email']
		username= utils.sanitize_username(email)

	# - Get all job ids from DB
	res= {}	
	collection_name= username + '.jobs'
	try:
		job_collection= mongo.db[collection_name]
		job_cursor= job_collection.find({},projection={"_id":0})
		res = list(job_cursor)

	except Exception as e:
		errmsg= 'Failed to get file ids from DB (err=' + str(e) + ')'
		res['status']= errmsg
		return make_response(jsonify(res),404)
		
	return make_response(jsonify(res),200)
	

#=================================
#===      JOB CANCEL 
#=================================
@job_status_bp.route('/job/<task_id>/cancel',methods=['GET','POST'])
@custom_require_login
def cancel_job(task_id):
	"""Cancel job """

	# - Init response
	res= {}
	res['status']= ''
	
	# - Get task
	task = background_task.AsyncResult(task_id)
	if not task or task is None:
		errmsg= 'No task found with id ' + task_id + '!'
		res['status']= errmsg
		return make_response(jsonify(res),404)

	# - Revoke task
	logger.info("Revoking task %s ..." % task_id)
	try:
		#task.revoke(task_id,terminate=True,signal='SIGKILL')
		#task.revoke(task_id,terminate=True,signal='SIGUSR1')
		#revoke(task_id, terminate=True,signal='SIGUSR1') # force celery task to go to SOFT TIME OUT
		revoke(task_id, terminate=True,signal='SIGTERM')
		
	except Exception as e:
		errmsg= 'Exception caught when attempting to rekove task ' + task_id + ' (err=' + str(e) + ')!' 
		logger.warn(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),500)

	# - Kill background process
	#   NB: This is not working if running in multi nodes
	pid= task.info.get('pid', '')
	res['status']= 'Task revoked'

	logger.info("Killing pid=%s ..." % pid)
	try:
		os.killpg(os.getpgid(int(pid)), signal.SIGKILL)  # Send the signal to all the process groups
		res['status']= 'Task revoked and background process canceled with success'

	except Exception as e:
		errmsg= 'Exception caught when attempting to kill background task process with PID=' + pid + ' (err=' + str(e) + ')!' 
		logger.warn(errmsg)
		res['status']= 'Task revoked but failed to cancel background process (err=' + str(e) + ')'
		
	return make_response(jsonify(res),200)


#=================================
#===      JOB STATUS HELPER
#=================================
def compute_job_status(task_id):
	""" Query job status from celery backend DB and adjust it """

	# - Init reply
	logger.info("Computing job status for task id=%s ..." % task_id)
	res= {}
	res['job_id']= task_id
	res['pid']= ''
	res['state']= ''
	res['status']= ''
	res['exit_code']= ''
	res['elapsed_time']= ''

	# - Get task
	task= None
	try:
		task = background_task.AsyncResult(task_id)
	except:
		errmsg= 'Failed to create instance of AsyncResult for task ' + task_id + '!'
		raise NameError(errmsg)	

	if not task or task is None:
		errmsg= 'No task found with id ' + task_id + '!'
		raise NameError(errmsg)
			
	# - Check if task ID not existing 
	#   NB: Celery does not throw exceptions in case task id is not known, it just set task state to PENDING, so try to handle this...wtf!
	if task.state=='PENDING' and (task.result==None or task.info==None): 
		errmsg= 'No task found with id ' + task_id + '!'
		raise NameError(errmsg)

	# - Celery set to SUCCESS whenever task return a value, even if update_state is set to FAILURE before return or if returning Ignore() or a <0 code so need to handle this case ... wtf!
	task_state= task.state 
	task_exit= task.info.get('exit_code', '')
	task_pid= task.info.get('pid', '')
	task_status= task.info.get('status', '')
	task_elapsed= task.info.get('elapsed_time', '')
	if task_state=='SUCCESS' and str(task_exit)!='0':
		if str(task_exit)=='124':
			task_state= 'TIMED-OUT'
		else:
			task_state= 'FAILURE'
	
	# - Fill task info
	res['pid']= task_pid
	res['state']= task_state
	res['status']= task_status
	res['exit_code']= task_exit
	res['elapsed_time']= task_elapsed

	return res


#=================================
#===      JOB STATUS 
#=================================
@job_status_bp.route('/job/<task_id>/status',methods=['GET'])
@custom_require_login
def get_job_status(task_id):
	""" Get job status """
    
	# - Init response
	res= {}
	res['job_id']= task_id
	res['pid']= ''
	res['state']= ''
	res['status']= ''
	res['exit_code']= ''
	res['elapsed_time']= ''

	# - Get aai info
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		email= g.oidc_token_info['email']
		username= utils.sanitize_username(email)

	# - Search job id in user collection
	collection_name= username + '.jobs'
	job= None
	try:
		job_collection= mongo.db[collection_name]
		job= job_collection.find_one({'job_id': str(task_id)})
	except Exception as e:
		errmsg= 'Exception catched when searching job id in DB (err=' + str(e) + ')!'
		logger.error(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)

	if not job or job is None:
		errmsg= 'Job ' + task_id + ' not found for user ' + username + '!'
		logger.warn(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)

	# - Retrieve job status from Mongo DB
	res['pid']= job['pid']
	res['state']= job['state']
	res['status']= job['status']
	res['exit_code']= job['exit_code']
	res['elapsed_time']= job['elapsed_time']

	##########################################################################
	##     ORIGINAL METHOD (RETRIEVE STATUS FROM CELERY RESULT BACKEND)
	#try:
	#	res= compute_job_status(task_id)
	#	return make_response(jsonify(res),200)

	#except NameError as e:
	#	res['status']= str(e)
	#	return make_response(jsonify(res),404)
	###########################################################################

	return make_response(jsonify(res),200)



#=================================
#===      JOB OUTPUT 
#=================================
@job_output_bp.route('/job/<task_id>/output',methods=['GET'])
@custom_require_login
def get_job_output(task_id):
	""" Get job output """

	# - Init response
	res= {}
	res['job_id']= task_id
	res['state']= ''
	res['status']= ''

	# - Get aai info
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		email= g.oidc_token_info['email']
		username= utils.sanitize_username(email)

	# - Check job status
	try:
		job_status= compute_job_status(task_id)
		
	except NameError as e:
		res['status']= str(e)
		return make_response(jsonify(res),404)
	
	# - If job state is PENDING/STARTED/RUNNING/ABORTED return 
	job_state= job_status['state']
	job_not_completed= (
		job_state=='RUNNING' or 
		job_state=='PENDING' or
		job_state=='STARTED' or 
		job_state=='ABORTED' 
	)
	if job_not_completed:
		logger.info("Job %s not completed (status=%s)..." % (task_id,job_state))
		res['state']= job_state
		res['status']= 'Job aborted or not completed, no output data available'
		return make_response(jsonify(res),202)

	# - Send file
	job_top_dir= current_app.config['JOB_DIR'] + '/' + username
	job_dir_name= 'job_' + task_id
	job_dir= os.path.join(job_top_dir,job_dir_name)
	tar_filename= 'job_' + task_id + '.tar.gz'
	tar_file= os.path.join(job_dir,tar_filename)

	logger.info("Sending tar file %s with job output data exists ..." % tar_file)
	
	try:
		return send_file(
			tar_file, 
			as_attachment=True
		)
	except FileNotFoundError:
		res['status']= 'Job output file ' + tar_filename + ' not found!'
		return make_response(jsonify(res),500)


	return make_response(jsonify(res),200)
	
