##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import glob
import signal
import sys
import json
import time
import datetime
import logging
import numpy as np
import subprocess

try:
	FileNotFoundError  # python3
except NameError:
	FileNotFoundError = IOError # python2

try:
	from urllib.request import urlopen
except ImportError:
	from urllib2 import urlopen

# Import flask modules
from flask import current_app, Blueprint, render_template, request, redirect, url_for
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
from werkzeug.utils import secure_filename

# Import celery modules
from celery import states
from celery.exceptions import Ignore, SoftTimeLimitExceeded

# Import Celery app
from caesar_rest.app import celery as celery_app
from caesar_rest import utils
#from caesar_rest.app import CustomTask

# Import mongo
from pymongo import MongoClient

#from flask import current_app


# Get logger
logger = logging.getLogger(__name__)

##############################
#   WORKERS
##############################
@celery_app.task(bind=True)
def background_task(self,app_name,cmd,cmd_args,job_top_dir,username='anonymous',db_host='localhost', db_port='27017', db_name='caesardb',monitoring_period=5):
	"""Background task """

	# - Initialize task info
	task_id= self.request.id.__str__()
	
	task_info= {
		'job_id': task_id, 
		'pid': '',
		'cmd': cmd,	
		'cmd_args': cmd_args,
		'state': 'PENDING',
		'status': 'Task pending to be executed',
		'elapsed_time': -1, 
		'exit_code': -1
	}

	res= {
		'job_id': task_id,	
		'pid': '',
		'cmd': cmd,
		'cmd_args': cmd_args,
		'exit_code': -1,
		'state': 'PENDING',
		'status': 'Task pending to be executed',
		'elapsed_time': -1
	}

	# - Connect to mongoDB	
	logger.info("Connecting to DB (dbhost=%s, dbname=%s, dbport=%s) ..." % (db_host,db_name,db_port))
	client= None
	db_port_int= int(db_port)
	try:
		client= MongoClient(db_host, db_port_int)
		#client= self.db
	except Exception as e:
		errmsg= 'Exception caught when connecting to DB server (err=' + str(e) + ')!' 
		logger.error(errmsg)
		task_info['state']= 'ABORTED'
		task_info['status']= errmsg
		res['state']= 'ABORTED'
		res['status']= errmsg
		res['exit_code']= 126
		self.update_state(state='ABORTED', meta=task_info)
		return res
		
	if client and client is not None:
		logger.info("Connected to db %s..." % db_name)
	else:
		errmsg= 'Cannot connect to DB server' 
		logger.error(errmsg)
		task_info['state']= 'ABORTED'
		task_info['status']= errmsg
		res['state']= 'ABORTED'
		res['status']= errmsg
		res['exit_code']= 126
		self.update_state(state='ABORTED', meta=task_info)
		return res
	
	# - Set init task state in DB
	logger.info("Updating task state (PENDING) in DB ...")
	if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
		logger.warn("Failed to update task state (PENDING) in DB!")

	# - Create job directory
	job_dir_name= 'job_' + task_id
	job_dir= os.path.join(job_top_dir,job_dir_name)

	logger.info("Creating job dir %s (top dir=%s) ..." % (job_dir,job_top_dir))
	try:
		os.makedirs(job_dir)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			errmsg= "Failed to create job directory " + job_dir + "!" 
			logger.error(errmsg)
			task_info['state']= 'ABORTED'
			task_info['status']= errmsg
			res['state']= 'ABORTED'
			res['status']= errmsg
			res['exit_code']= 126
			self.update_state(state='ABORTED', meta=task_info)
			logger.info("Updating task state (ABORTED) in DB ...")
			if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
				logger.warn("Failed to update task state (ABORTED) in DB!")

			return res
	
	# - Execute command
	logger.info("Executing cmd %s with args %s ..." % (cmd,cmd_args))
	self.update_state(state='PENDING', meta=task_info)
	
	exec_cmd= ' '.join([cmd,cmd_args])
	
	env= os.environ.copy()

	p= subprocess.Popen(exec_cmd, shell=True, cwd=job_dir, preexec_fn=os.setsid, env=env, executable='/bin/bash')
	pid= p.pid
	
	logger.info("Bkg task started with pid=%s ..." % str(pid))
	start = time.time()
	
	res['pid']= str(pid)
	task_info['state']= 'STARTED'
	task_info['status']= 'Task started in background'
	task_info['pid']= str(pid)
	self.update_state(state='STARTED', meta=task_info)

	logger.info("Updating task state (STARTED) in DB ...")
	if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
		logger.warn("Failed to update task state (STARTED) in DB!")


	# - Monitor long task catching soft time limit
	waitTime= monitoring_period
	last_status= task_info['status']
	last_state= task_info['state']

	try:
		try:
			while True:
				logger.debug("Checking process status ...")
				if p.poll() is None:
					logger.info("Task %s (pid=%d) is still running ..." % (task_id,pid))
					elapsed = time.time() - start

					task_info['state']= 'RUNNING'
					task_info['status']= 'Task running in background'
					task_info['elapsed_time']= elapsed
					self.update_state(state='RUNNING', meta=task_info)

					# - Update state & status in DB
					#if task_info['state']!=last_state or task_info['status']!=last_status:
					logger.info("Updating task state (RUNNING) in DB ...")
					if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
						logger.warn("Failed to update task state (RUNNING) in DB!")

					last_status= task_info['status']
					last_state= task_info['state']
				
					# - Sleeping a bit before retrying again
					time.sleep(waitTime)
				
				else:
					break

		except SoftTimeLimitExceeded:
			logger.info("Task exceeded time limits, killing proc %d ..." % pid)
			#os.kill(pid, signal.SIGTERM)
			os.killpg(os.getpgid(pid), signal.SIGTERM)  # Send the signal to all the process groups

			status_msg= "Task exceeded time limits"
			logger.info(status_msg)
			elapsed = time.time() - start
			task_info['state']= 'TIMED-OUT'
			task_info['status']= status_msg
			task_info['elapsed_time']= elapsed
			self.update_state(state='TIMED-OUT', meta=task_info)
			res['exit_code']= 124 # equivalent sigterm
			res['status']= status_msg
			res['elapsed_time']= elapsed

			logger.info("Updating task state (TIMED-OUT) in DB ...")
			if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
				logger.warn("Failed to update task state (TIMED-OUT) in DB!")
	
			return res

	except KeyboardInterrupt:
		logger.info("Task monitoring interrupted with ctrl-c signal")		
		raise Ignore()		

	# - Create a tar.gz with job files (output, logs, submission scripts, etc)
	tar_filename= 'job_' + task_id + '.tar.gz'
	tar_file= os.path.join(job_dir,tar_filename)
	logger.info("Creating a tar file %s with job output data ..." % tar_file)
	utils.make_tar(tar_file,job_dir)

	# - Check return code after task finish
	end = time.time()
	elapsed = end - start	
	task_state= 'SUCCESS'
	status_msg= ''

	if p.returncode<0: # Process failed
		task_state= 'FAILURE'
		status_msg= "Process terminated with SIG " + str(p.returncode)
		logger.info(status_msg)
		#raise Ignore()

	elif p.returncode==0: # Process success
		task_state= 'SUCCESS'
		status_msg= "Process terminated with success"
		logger.info(status_msg)		
		
	else: # Process failed (not returning =0)
		task_state= 'FAILURE'
		status_msg= "Process terminated with return code " + str(p.returncode)
		logger.info(status_msg)
		#raise Ignore()

	task_info['state']= task_state
	task_info['status']= status_msg
	task_info['elapsed_time']= elapsed
	task_info['exit_code']= p.returncode
	self.update_state(state=task_state, meta=task_info)

	logger.info("Updating task state (%s) in DB ..." % task_info['state'])
	if update_job_status_in_db(client, db_name, task_id, task_info, username)<0:
		logger.warn("Failed to update task state (%s) in DB!" % task_info['state'])
	
	# - Execute post actions (in case of SUCCESS)
	if p.returncode==0:
		logger.info("Executing post actions after task %s success..." % task_id)
		if do_post_actions(job_dir, app_name, cmd, cmd_args)<0:
			logger.warn("Post actions failed for task %s" % task_id)

	# - Reply to client	
	res= {
		'job_id': task_id,
		'pid': str(pid),
		'cmd': cmd,
		'cmd_args': cmd_args,
		'exit_code': p.returncode, 
		'state': task_state, 
		'status': status_msg, 
		'elapsed_time': elapsed
	}

	return res


def update_job_status_in_db(client, db_name, task_id, task_info, username='anonymous'):
	""" Update job status in DB """

	# - Search job id in user collection
	if client.db_name is None:
		logger.error("mongo db instance is None!")	
		return -1
	collection_name= username + '.jobs'

	# - Update task info
	state= task_info['state']	
	status= task_info['status']
	exit_code= task_info['exit_code']
	elapsed_time= task_info['elapsed_time']
	pid= task_info['pid']

	try:
		job_collection= client[db_name][collection_name]
		job_collection.update_one({'job_id':task_id},{'$set':{'state':state,'status':status,'exit_code':exit_code,'elapsed_time':elapsed_time,'pid':pid}},upsert=False)
	except Exception as e:
		errmsg= 'Exception caught when updating job ' + str(task_id) + ' in DB (err=' + str(e) + ')!'
		logger.error(errmsg)
		return -1

	return 0



def do_post_actions(job_dir,app_name,cmd,cmd_args):
	""" Execute job post actions """

	if app_name=='sfinder':
		return do_sfinder_post_actions(job_dir,app_name,cmd,cmd_args)	
	# ... Add others

	return 0

def do_sfinder_post_actions(job_dir,app_name,cmd,cmd_args):
	""" Execute sfinder post actions """
	
	# - Parse options and get input filename
	cmd_args_list= cmd_args.split()
	print(cmd_args)
	print(cmd_args_list)
	matching= [s for s in cmd_args_list if "--inputfile=" in s]
	print(matching)
	logger.info("")
	if not matching:
		logger.warn("Can't find --inputfile option in given cmd args, stop post action.")
		return -1
	inputimg= matching[0].replace('--inputfile=','')

	# - Search for region files in job directory
	regionfiles= []
	os.chdir(job_dir)
	for filename in glob.glob("*.reg"):
		regionfiles.append(filename)
	logger.info("#%d region files found in dir %s..." % (len(regionfiles),job_dir))

	# - Draw and save image+regions
	zmin= 0
	zmax= 0
	contrast= 0.3
	cmap= "afmhot"
	save= True
	outfile="plot.png"

	status= utils.plot_img_and_regions(
		inputimg,
		regionfiles,
		zmin=zmin, zmax= zmax,
		cmap= cmap,
		contrast=contrast,
		save=save,
		outfile=outfile
	)	

	if status<0:
		logger.warn("Failed to draw and save img+regions!")
		return -1

	return 0

