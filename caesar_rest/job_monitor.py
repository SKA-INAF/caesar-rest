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
import datetime

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
from caesar_rest import jobmgr_kube

# Import mongo
from pymongo import MongoClient



# Get logger
logger = logging.getLogger(__name__)

##############################
#   WORKERS
##############################
@celery_app.task(bind=True)
def jobmonitor_task(self):
	""" job monitoring task """

	logger.info("Executing job monitoring task ...")

	# - Check first required env variables
	DB_NAME= os.environ.get('CAESAR_REST_DBNAME')
	DB_HOST= os.environ.get('CAESAR_REST_DBHOST')
	DB_PORT= os.environ.get('CAESAR_REST_DBPORT')
	JOB_DIR= os.environ.get('CAESAR_REST_JOBDIR')
	DATA_DIR= os.environ.get('CAESAR_REST_DATADIR')
	
	if DB_NAME is None or DB_NAME=="":
		logger.warn("Env var CAESAR_REST_DBNAME not defined, please set it to backend DB name...")
		return
	if DB_HOST is None or DB_HOST=="":
		logger.warn("Env var CAESAR_REST_DBHOST not defined, please set it to backend DB hostname...")
		return	
	if DB_PORT is None or DB_PORT=="":
		logger.warn("Env var CAESAR_REST_DBPORT not defined, please set it to backend DB port...")
		return	
	if JOB_DIR is None or JOB_DIR=="":
		logger.warn("Env var CAESAR_REST_JOBDIR not defined, please set it to job top dir name ...")
		return
	if DATA_DIR is None or DATA_DIR=="":
		logger.warn("Env var CAESAR_REST_DATADIR not defined, please set it to data top dir name ...")
		return

	# - Connect to mongoDB	
	logger.info("Connecting to DB (dbhost=%s, dbname=%s, dbport=%s) ..." % (DB_PORT,DB_NAME,DB_PORT))
	client= None
	DB_PORT_INT= int(DB_PORT)
	try:
		client= MongoClient(DB_HOST, DB_PORT_INT)
	except Exception as e:
		errmsg= 'Exception caught when connecting to DB server (err=' + str(e) + ')!' 
		logger.error(errmsg)
		return
		
	if client and client is not None:
		logger.info("Connected to db %s..." % DB_NAME)
	else:
		errmsg= 'Cannot connect to DB server' 
		logger.error(errmsg)
		return

	# - Get all job collections from DB
	logger.info("Getting all job collection names from DB ...")
	collection_names= []
	try:
		collection_names= db.list_collection_names(filter={"name":{"$regex": ".jobs"}})
	except Exception as e:
		logger.warn("Failed to get job collection names from DB!")
		return

	print("--> collection_names")
	print(collection_names)

	# - Loop over collection names and get all PENDING/STARTED/RUNNING jobs	
	for collection_name in collection_names:

		job_list= []
		job_collection= None

		try:
			job_collection= client[DB_NAME][collection_name]
			job_cursor= job_collection.find({})
			job_cursor= job_collection.find(
				{"$or": [
					{"state":"PENDING"},{"state":"STARTED"},{"state":"RUNNING"}
				]
				}
			)

			if job_cursor is not None:
				job_list = list(job_cursor)

		except Exception as e:
			errmsg= 'Failed to get jobs from DB for collection ' + collection_name + ' (err=' + str(e) + ')'
			logger.error(errmsg)
			continue

		if not job_list:
			logger.info("No unfinished jobs to be check for collection %s ..." % collection_name)
			continue
			
		# - Process list and get job statuses from scheduler
		for job_obj in job_list:
			job_id= job_obj['job_id']

			# - Check job scheduler field
			if 'scheduler' not in job_obj:
				continue
			job_scheduler= job_obj['scheduler']

			# - Skip celery scheduler because these jobs are monitored by celery tasks
			if job_scheduler=='celery':
				continue

			# - Update Kubernetes job status
			job_moni_status= -1
			if job_scheduler=='kubernetes':
				job_moni_status= monitor_kubernetes_job(job_id, job_collection)
			elif job_scheduler=='slurm':
				job_moni_status= monitor_kubernetes_job(job_id, job_collection)	
			else:
				logger.warn("Invalid/unknown job scheduler (%s), skip job moni..." % job_scheduler)
				continue

			if job_moni_status<0:
				logger.warn("Failed to monitor %s job %s, skip to next..." % (job_scheduler, job_id))
				continue



####################################
##   MONITOR KUBERNETES JOB
####################################
def monitor_kubernetes_job(job_id, job_collection):
	""" Monitor and update job status in DB """

	# - Check job collection
	if job_collection is None:
		logger.warn("Given mongo job collection is None!")
		return -1

	# - Check kube client instance
	if jobmgr_kube is None:
		logger.warn("Kube client is None!")
		return -1

	# - Get Kube job status
	try:
		res= jobmgr_kube.get_job_status(job_id)
	except Exception as e:
		logger.warn("Failed to retrieve job %s status (err=%s)" % (job_id, str(e)))
		return -1

	# - Check result
	if not res:
		logger.warn("Empty dict returned from kube client get_job_status(), cannot update job!")
		return -1
		
	state= res['state']
	status= res['status']
	elapsed_time= res['elapsed_time']
			
	# - Update job status
	try:
		job_collection.update_one({'job_id':job_id},{'$set':{'state':state,'status':status,'elapsed_time':elapsed_time}},upsert=False)
	except Exception as e:
		errmsg= 'Exception caught when updating job ' + str(job_id) + ' in DB (err=' + str(e) + ')!'
		logger.warn(errmsg)
		return -1

	# - If SUCCESS or FAILURE clear the pod
	#   NB: ttl option not working when job is SUCCESS.
	if state=='SUCCESS' or state=='FAILURE':
		try:
			res= jobmgr_kube.delete_job(job_id)
		except Exception as e:
			logger.warn("Failed to delete job %s (err=%s)" % (job_id, str(e)))
			return -1
	
	return 0


####################################
##   MONITOR SLURM JOB
####################################
def monitor_slurm_job(job_id, job_collection):
	""" Monitor and update job status in DB """
	
	# IMPLEMENT ME!!!
	# ...
	# ...

	return 0



	
