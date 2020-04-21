##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
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
from celery.exceptions import Ignore

# Import Celery app
from caesar_rest.app import celery as celery_app

# Get logger
logger = logging.getLogger(__name__)

##############################
#   WORKERS
##############################
@celery_app.task(bind=True)
def background_task(self,cmd,cmd_args):
	"""Background task """

	# - Get access to task id
	task_id= self.request.id.__str__()

	task_info= {
		'job_id': task_id, 
		'cmd': cmd,	
		'cmd_args': cmd_args,
		'status': 'Task pending to be executed',
		'elapsed_time': '0', 
		'exit_code': ''
	}

	logger.info("Executing cmd %s with args %s ..." % (cmd,cmd_args))
	self.update_state(state='PENDING', meta=task_info)

	exec_cmd= ' '.join([cmd,cmd_args])
	
	#p= subprocess.Popen([cmd,cmd_args], shell=True,universal_newlines=True, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
	p= subprocess.Popen(exec_cmd, shell=True)
	#output, err = process.communicate()
	logger.info("Bkg task started  ...")
	start = time.time()
	
	task_info['status']= 'Task started in background'
	self.update_state(state='STARTED', meta=task_info)

	time.sleep(20)


	# - Monitor task status 
	waitTime= 3
	try:
		while True:

			logger.info("Checking process status ...")
			if p.poll() is None:
				logger.info("Process is still running ...")
				elapsed = time.time() - start

				task_info['status']= 'Task running in background'
				task_info['elapsed']= str(elapsed)
				self.update_state(state='RUNNING', meta=task_info)

				# - Sleeping a bit before retrying again
				time.sleep(waitTime)
				
			else:
				break
					
	except KeyboardInterrupt:
		logger.info("Task monitoring interrupted with ctrl-c signal")		
		raise Ignore()

	# - Check return code after task finish
	res= {}
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
		'cmd': cmd,
		'cmd_args': cmd_args,
		'exit_code': p.returncode, 
		'status': status_msg, 
		'elapsed_time': str(elapsed)
	}

	return res


