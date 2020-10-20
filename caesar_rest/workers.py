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

# Get logger
logger = logging.getLogger(__name__)

##############################
#   WORKERS
##############################
@celery_app.task(bind=True)
def background_task(self,cmd,cmd_args,job_top_dir):
	"""Background task """

	# - Initialize task info
	task_id= self.request.id.__str__()
	
	task_info= {
		'job_id': task_id, 
		'pid': '',
		'cmd': cmd,	
		'cmd_args': cmd_args,
		'status': 'Task pending to be executed',
		'elapsed_time': '0', 
		'exit_code': ''
	}

	res= {
		'job_id': task_id,	
		'pid': '',
		'cmd': cmd,
		'cmd_args': cmd_args,
		'exit_code': '',
		'status': 'Task pending to be executed',
		'elapsed_time': '0'
	}

	# - Create job directory
	job_dir_name= 'job_' + task_id
	job_dir= os.path.join(job_top_dir,job_dir_name)

	logger.info("Creating job dir %s ..." % job_dir)
	try:
		os.makedirs(job_dir)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			errmsg= "Failed to create job directory " + job_dir + "!" 
			logger.error(errmsg)
			task_info['status']= errmsg
			res['status']= errmsg
			res['exit_code']= 126
			self.update_state(state='ABORTED', meta=task_info)
			
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
	task_info['status']= 'Task started in background'
	task_info['pid']= str(pid)
	self.update_state(state='STARTED', meta=task_info)


	# - Monitor long task catching soft time limit
	waitTime= 3
	try:
		try:
			while True:
				logger.debug("Checking process status ...")
				if p.poll() is None:
					logger.info("Task %s (pid=%d) is still running ..." % (task_id,pid))
					elapsed = time.time() - start

					task_info['status']= 'Task running in background'
					task_info['elapsed']= str(elapsed)
					self.update_state(state='RUNNING', meta=task_info)
				
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
			task_info['status']= status_msg
			task_info['elapsed']= str(elapsed)
			self.update_state(state='TIMED-OUT', meta=task_info)
			res['exit_code']= 124 # equivalent sigterm
			res['status']= status_msg
			res['elapsed_time']= str(elapsed)
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

	task_info['status']= status_msg
	task_info['elapsed']= str(elapsed)
	task_info['exit_code']= p.returncode
	self.update_state(state=task_state, meta=task_info)
	res= {
		'job_id': task_id,
		'pid': str(pid),
		'cmd': cmd,
		'cmd_args': cmd_args,
		'exit_code': p.returncode, 
		'status': status_msg, 
		'elapsed_time': str(elapsed)
	}

	return res


