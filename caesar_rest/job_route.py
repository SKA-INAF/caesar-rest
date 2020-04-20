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

# Import Celery app
from caesar_rest.app import celery as celery_app
from caesar_rest.workers import background_task

# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINTS
##############################
job_bp = Blueprint('job', __name__,url_prefix='/caesar/api/v1.0')
job_status_bp = Blueprint('job_status', __name__,url_prefix='/caesar/api/v1.0')




@job_bp.route('/job', methods=['POST'])
def submit_job():
	""" Submit a job asyncronously """
	
	res= {}
	res['status']= ''
	res['app']= ''
	res['job_id']= ''
	res['submit_date']= ''

	# - Get request data
	req_data = request.get_json(silent=True)
	logger.info("Received job data %s " % str(req_data))

	app_name = req_data['app']
	job_inputs = req_data['job_inputs']
	if not app_name:
		logger.error("No app name given!")
		res['status']= 'No app name found in request!'
		return make_response(jsonify(res),400)

	if not job_inputs:
		logger.error("No job inputs given!")
		res['app']= app_name
		res['status']= 'No job inputs name found in request!'
		return make_response(jsonify(res),400)

	# - Submit task async	
	logger.info("Submitting job %s async ..." % app_name)
	now = datetime.datetime.now()
	submit_date= now.isoformat()

	task = background_task.apply_async([app_name,job_inputs])
	job_id= task.id
	logger.info("Submitted job with id=%s ..." % job_id)

	# ...
	# ...

	# - Fill response
	res['job_id']= job_id
	res['submit_date']= submit_date
	res['app']= app_name
	res['job_inputs']= job_inputs
		
	return make_response(jsonify(res),202)



#@app.route('/longtask', methods=['POST'])
#def longtask():
#	task = long_task.apply_async()
#	return jsonify({}), 202, {'Location': url_for('taskstatus',task_id=task.id)}


@job_status_bp.route('/job/<task_id>/status',methods=['GET'])
def get_job_status(task_id):
	""" Get job status """
    
	# - Init response
	res= {}
	res['job_id']= task_id
	res['state']= ''
	res['status']= ''
	res['exit_status']= ''
	res['elapsed_time']= ''


	# - Get task 
	task = background_task.AsyncResult(task_id)
	if not task:
		res['status']= 'No task found with given id'
		return make_response(jsonify(res),404)
	
	#print("Task type")
	#print(type(task.info))
	#print(task.info)
	#print("Task state=%s" % task.state)
	#print("Task result=%s" % task.result)

	# - Check if task ID not existing 
	#   NB: Celery does not throw exceptions in case task id is not known, it just set task state to PENDING, so try to handle this...wtf!
	if task.state=='PENDING' and (task.result==None or task.info==None): 
		res['status']= 'No task found with id ' + task_id + '!'
		return make_response(jsonify(res),404)
		
	# - Celery set to SUCCESS whenever task return a value, even if update_state is set to FAILURE before return or if returning Ignore() or a <0 code so need to handle this case ... wtf!
	task_state= task.state 
	task_exit= task.info.get('exit_code', '')
	task_status= task.info.get('status', '')
	task_elapsed= task.info.get('elapsed_time', '')
	if task_state=='SUCCESS' and task_exit!='0':
		task_state= 'FAILURE'
	
	# - Fill task info
	res['state']= task_state
	res['status']= task_status
	res['exit_status']= task_exit
	res['elapsed_time']= task_elapsed
	
	return make_response(jsonify(res),200)

