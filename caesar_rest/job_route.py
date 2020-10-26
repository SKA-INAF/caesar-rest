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
from flask import current_app, Blueprint, render_template, request, redirect, url_for, flash
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
from caesar_rest.decorators import custom_require_login
from caesar_rest import mongo

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
	res['app']= ''
	res['job_id']= ''
	res['submit_date']= ''

	# - Get aai info
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

	# - Get mongo info
	mongo_enabled= current_app.config['USE_MONGO']
	has_mongo= (mongo is not None)
	use_mongo= (mongo_enabled and has_mongo)

	# - Get request data
	req_data = request.get_json(silent=True)
	if not req_data:
		logger.error("Invalid request data!")
		res['status']= 'Invalid request data!'
		return make_response(jsonify(res),400)
	logger.info("Received job data %s " % str(req_data))

	app_name = req_data['app']
	job_inputs = req_data['job_inputs']
	if not app_name:
		logger.error("No app name given!")
		res['status']= 'No app name found in request!'
		return make_response(jsonify(res),400)

	res['app']= app_name

	if not job_inputs:
		logger.error("No job inputs given!")		
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
	if not cmd or not cmd_arg_list: 
		logger.warn("Job input validation failed!")
		res['status']= val_status
		return make_response(jsonify(res),400)

	cmd_args= ''
	if cmd_arg_list:
		cmd_args= ' '.join(cmd_arg_list)

	# - Submit task async	
	logger.info("Submitting job %s async (cmd=%s, args=%s) ..." % (app_name,cmd,cmd_args))
	now = datetime.datetime.now()
	submit_date= now.isoformat()
	#job_top_dir= current_app.config['JOB_DIR']
	job_top_dir= current_app.config['JOB_DIR'] + '/' + username

	task = background_task.apply_async([cmd,cmd_args,job_top_dir])
	job_id= task.id
	logger.info("Submitted job with id=%s ..." % job_id)

	# - Register task id in mongo
	if use_mongo:
		logger.info("Creating job object for task %s ..." % job_id)
		job_obj= {
			"job_id": job_id,
			"submit_date": submit_date,
			"app": app_name,	
			"job_inputs": job_inputs,
			"metadata": '', # FIX ME
			"tag": ''	# FIX ME
		}

		collection_name= username + '.jobs'

		try:
			logger.info("Creating or retrieving job collection for user %s ..." % username)
			job_collection= mongo.db[collection_name]

			logger.info("Adding job obj to collection ...")
			item_id= job_collection.insert(job_obj)
		
		except:
			logger.warn("Failed to create and register job in DB!")
			flash('Job submitted but failed to be registered in DB!')
			logger.warn("Job %s submitted but failed to be registered in DB!" % job_id)
			res['status']= 'Job submitted but failed to be registered in DB'
			return make_response(jsonify(res),500)


	# - Fill response
	res['job_id']= job_id
	res['submit_date']= submit_date
	res['app']= app_name
	res['job_inputs']= job_inputs
	res['status']= 'Job submitted with success'
	
	return make_response(jsonify(res),202)


#=================================
#===      JOB IDs 
#=================================
@job_bp.route('/jobs', methods=['GET'])
@custom_require_login
def get_job_ids():
	""" Retrieve all job ids per user """

	# - Get aai info
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

	# - Get mongo info
	mongo_enabled= current_app.config['USE_MONGO']
	has_mongo= (mongo is not None)
	use_mongo= (mongo_enabled and has_mongo)

	# - Get all job ids.
	#   NB: Only supported with Mongo backend
	d= {}	
	collection_name= username + '.jobs'
	if use_mongo:
		job_collection= mongo.db[collection_name]
		job_ids= job_collection.find().distinct('job_id')
		job_id_list= [str(jobid) for jobid in job_ids]
		d.update({'job_ids':job_id_list})

	else:
		d['status']= 'Server is running without MongoDB backend, so this functionality is not supported'
		d['job_ids']= []
		return make_response(jsonify(d),404)
		
	return make_response(jsonify(d),200)
	

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
	#task.revoke(task_id,terminate=True,signal='SIGKILL')
	#task.revoke(task_id,terminate=True,signal='SIGUSR1')
	revoke(task_id, terminate=True,signal='SIGTERM')
	#revoke(task_id, terminate=True,signal='SIGUSR1') # force celery task to go to SOFT TIME OUT

	# - Kill background process
	pid= task.info.get('pid', '')
	logger.info("Killing pid=%s ..." % pid)
	os.killpg(os.getpgid(int(pid)), signal.SIGKILL)  # Send the signal to all the process groups

	res['status']= 'Task canceled with success'
	return make_response(jsonify(res),200)


#=================================
#===      JOB STATUS HELPER
#=================================
def compute_job_status(task_id):
	""" Compute job status """

	# - Init reply
	logger.info("Computing job status for task id=%s ..." % task_id)
	res= {}
	res['job_id']= task_id
	res['pid']= ''
	res['state']= ''
	res['status']= ''
	res['exit_status']= ''
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
	res['exit_status']= task_exit
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
	res['exit_status']= ''
	res['elapsed_time']= ''

	# - Get aai info
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

	# - Get mongo info
	mongo_enabled= current_app.config['USE_MONGO']
	has_mongo= (mongo is not None)
	use_mongo= (mongo_enabled and has_mongo)

	# - Search job id in user collection
	collection_name= username + '.jobs'
	if use_mongo:
		job_collection= mongo.db[collection_name]
		job= job_collection.find_one({'job_id': str(task_id)})
		if not job or job is None:
			errmsg= 'Job ' + task_id + ' not found for user ' + username + '!'
			logger.warn(errmsg)
			res['status']= errmsg
			return make_response(jsonify(res),404)

	# - Retrieve job status
	try:
		res= compute_job_status(task_id)
		return make_response(jsonify(res),200)

	except NameError as e:
		res['status']= str(e)
		return make_response(jsonify(res),404)
	

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
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

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
	#job_top_dir= current_app.config['JOB_DIR']
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
	
