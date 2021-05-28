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
from caesar_rest import jobmgr_slurm

# Import mongo
from pymongo import MongoClient


# Get logger
#logger = logging.getLogger(__name__)
from caesar_rest import logger

##############################
#   WORKERS
##############################
@celery_app.task(bind=True)
def jobmonitor_task(self):
	""" job monitoring task """

	logger.info("Executing job monitoring task ...", action="jobmonitor")

	# - Check first required env variables
	DB_NAME= os.environ.get('CAESAR_REST_DBNAME')
	DB_HOST= os.environ.get('CAESAR_REST_DBHOST')
	DB_PORT= os.environ.get('CAESAR_REST_DBPORT')
	
	if DB_NAME is None or DB_NAME=="":
		logger.warn("Env var CAESAR_REST_DBNAME not defined, please set it to backend DB name...", action="jobmonitor")
		return
	if DB_HOST is None or DB_HOST=="":
		logger.warn("Env var CAESAR_REST_DBHOST not defined, please set it to backend DB hostname...", action="jobmonitor")
		return	
	if DB_PORT is None or DB_PORT=="":
		logger.warn("Env var CAESAR_REST_DBPORT not defined, please set it to backend DB port...", action="jobmonitor")
		return	
	
	# - Connect to mongoDB	
	logger.info("Connecting to DB (dbhost=%s, dbname=%s, dbport=%s) ..." % (DB_PORT,DB_NAME,DB_PORT), action="jobmonitor")
	client= None
	DB_PORT_INT= int(DB_PORT)
	try:
		client= MongoClient(DB_HOST, DB_PORT_INT)
	except Exception as e:
		errmsg= 'Exception caught when connecting to DB server (err=' + str(e) + ')!' 
		logger.error(errmsg, action="jobmonitor")
		return
		
	if client and client is not None:
		logger.info("Connected to db %s..." % DB_NAME, action="jobmonitor")
	else:
		errmsg= 'Cannot connect to DB server' 
		logger.error(errmsg, action="jobmonitor")
		return

	# - Get all job collections from DB
	logger.info("Getting all job collection names from DB ...", action="jobmonitor")
	collection_names= []
	try:
		collection_names= client[DB_NAME].list_collection_names(filter={"name":{"$regex": ".jobs"}})
	except Exception as e:
		logger.warn("Failed to get job collection names from DB (err=%s)!" % str(e), action="jobmonitor")
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
			logger.error(errmsg, action="jobmonitor")
			continue

		if not job_list:
			logger.info("No unfinished jobs to be check for collection %s ..." % collection_name, action="jobmonitor")
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
				job_moni_status= monitor_kubernetes_job(job_obj, job_collection)
			elif job_scheduler=='slurm':
				job_moni_status= monitor_slurm_job(job_obj, job_collection)	
			else:
				logger.warn("Invalid/unknown job scheduler (%s), skip job moni..." % job_scheduler, action="jobmonitor")
				continue

			if job_moni_status<0:
				logger.warn("Failed to monitor %s job %s, skip to next..." % (job_scheduler, job_id), action="jobmonitor")
				continue

####################################
##   MONITOR JOBS
####################################
def monitor_jobs(db):
	""" Monitor jobs stored in DB """

	# - Check DB instance
	if db is None:
		logger.error("None DB instance given!", action="jobmonitor")
		return -1

	# - Get all job collections from DB
	logger.info("Getting all job collection names from DB ...", action="jobmonitor")
	collection_names= []
	try:
		collection_names= db.list_collection_names(filter={"name":{"$regex": ".jobs"}})
	except Exception as e:
		logger.warn("Failed to get job collection names from DB (err=%s)!" % str(e), action="jobmonitor")
		return -1

	print("--> collection_names")
	print(collection_names)

	# - Loop over collection names and get all PENDING/STARTED/RUNNING jobs	
	for collection_name in collection_names:

		job_list= []
		job_collection= None

		try:
			job_collection= db[collection_name]
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
			logger.error(errmsg, action="jobmonitor")
			continue

		if not job_list:
			logger.info("No unfinished jobs to be check for collection %s ..." % collection_name, action="jobmonitor")
			continue
			
		# - Process list and get job statuses from scheduler
		kube_jobs= []
		slurm_jobs= []
		
		for job_obj in job_list:

			# - Check job obj
			if not job_obj or job_obj is None:
				logger.warn("Skip current job obj as None or empty ...", action="jobmonitor")	
				continue

			job_id= job_obj['job_id']

			# - Check job scheduler field
			if 'scheduler' not in job_obj:
				continue
			job_scheduler= job_obj['scheduler']

			# - Skip celery scheduler because these jobs are monitored by celery tasks
			if job_scheduler=='celery':
				continue

			# - Fill kube jobs to be monitored
			if job_scheduler=='kubernetes':
				kube_jobs.append(job_obj)
			elif job_scheduler=='slurm':
				slurm_jobs.append(job_obj)
			else:
				logger.warn("Invalid/unknown job scheduler (%s), skip job moni..." % job_scheduler, action="jobmonitor")
				continue
	
			# - Update Kubernetes job status
			#job_moni_status= -1
			#if job_scheduler=='kubernetes':
			#	job_moni_status= monitor_kubernetes_job(job_obj, job_collection)
			#elif job_scheduler=='slurm':
			#	job_moni_status= monitor_slurm_job(job_obj, job_collection)	
			#else:
			#	logger.warn("Invalid/unknown job scheduler (%s), skip job moni..." % job_scheduler, action="jobmonitor")
			#	continue

			#if job_moni_status<0:
			#	logger.warn("Failed to monitor %s job %s, skip to next..." % (job_scheduler, job_id), action="jobmonitor")
			#	continue
	
		# - Update Kubernetes job status	
		for job_obj in kube_jobs:
			job_id= job_obj['job_id']
			if monitor_kubernetes_job(job_obj, job_collection)<0:
				logger.warn("Failed to monitor Kube job %s, skip to next..." % (job_id), action="jobmonitor")
				continue

		# - Update slurm jobs status
		if slurm_jobs:
			if monitor_slurm_jobs(slurm_jobs, job_collection)<0:
				logger.warn("Failed to monitor Slurm jobs ...", action="jobmonitor")
				


	return 0
	

####################################
##   MONITOR KUBERNETES JOB
####################################
def monitor_kubernetes_job(job_obj, job_collection):
	""" Monitor and update job status in DB """

	# - Extract field
	if not job_obj or job_obj is None:
		logger.warn("Given job obj is None or empty!", action="jobmonitor")	
		return -1		
	job_id= job_obj['job_id']
	job_dir_name= 'job_' + job_id
	tar_filename= 'job_' + job_id + '.tar.gz'
	job_top_dir= ''
	job_dir= ''
	tar_file= ''
	job_dir_existing= False
	tar_file_existing= False
	if 'job_top_dir' in job_obj:
		job_top_dir= job_obj['job_top_dir']
		job_dir= os.path.join(job_top_dir,job_dir_name)
		tar_file= os.path.join(job_dir,tar_filename)
		job_dir_existing= os.path.isdir(job_dir)
		tar_file_existing= os.path.isfile(tar_file)

	# - Check job collection
	if job_collection is None:
		logger.warn("Given mongo job collection is None!", action="jobmonitor")
		return -1

	# - Check kube client instance
	if jobmgr_kube is None:
		logger.warn("Kube client is None!", action="jobmonitor")
		return -1

	# - Get Kube job status
	try:
		res= jobmgr_kube.get_job_status(job_id)
	except Exception as e:
		logger.warn("Failed to retrieve job %s status (err=%s)" % (job_id, str(e)), action="jobmonitor")
		return -1

	# - Check result
	if not res:
		logger.warn("Empty dict returned from kube client get_job_status(), cannot update job!", action="jobmonitor")
		return -1
		
	state= res['state']
	status= res['status']
	elapsed_time= res['elapsed_time']

	# - Create tar file with job output if job completed
	if state=='SUCCESS' or state=='FAILURE':
		if job_dir_existing and tar_file!="":
			if tar_file_existing:
				logger.info("Job %s output tar file %s already existing, won't create it again ..." % (job_id, tar_file), action="jobmonitor")
			else:
				logger.info("Creating a tar file %s with job output data ..." % tar_file, action="jobmonitor")
				utils.make_tar(tar_file, job_dir)
		else:
			logger.warn("Won't create output data tar file %s as job output directory %s not found ..." % (tar_file, job_dir), action="jobmonitor")

			
	# - Update job status
	try:
		logger.info("Updating job %s state to %s (status=%s) ..." % (job_id, state, status), action="jobmonitor")
		job_collection.update_one({'job_id':job_id},{'$set':{'state':state,'status':status,'elapsed_time':elapsed_time}},upsert=False)
	except Exception as e:
		errmsg= 'Exception caught when updating job ' + str(job_id) + ' in DB (err=' + str(e) + ')!'
		logger.warn(errmsg, action="jobmonitor")
		return -1

	# - If SUCCESS or FAILURE clear the pod
	#   NB: ttl option not working when job is SUCCESS.
	if state=='SUCCESS' or state=='FAILURE':

		# - Clearing job state
		logger.info("Clearing job %s (state=%s) ..." % (job_id, state), action="jobmonitor")
		try:
			res= jobmgr_kube.delete_job(job_id)
		except Exception as e:
			logger.warn("Failed to delete job %s (err=%s)" % (job_id, str(e)), action="jobmonitor")
			return -1
	
	return 0


####################################
##   MONITOR SLURM JOB
####################################
def monitor_slurm_jobs(job_objs, job_collection):
	""" Monitor and update job status in DB """

	# - Check Slurm client instance
	if jobmgr_slurm is None:
		logger.warn("Slurm client is None!", action="jobmonitor")
		return -1

	# - Check job collection
	if job_collection is None:
		logger.warn("Given mongo job collection is None!", action="jobmonitor")
		return -1

	# - Check job objs
	if not job_objs or job_objs is None:
		logger.warn("Given job objs is None or empty!", action="jobmonitor")	
		return -1

	# - Find list of job pids to be monitored
	job_pids= []
	for job_obj in job_objs:
		job_id= job_obj['job_id']
		job_pid= str(job_obj['pid'])
		if job_pid=="":
			logger.warn("Current Slurm job pid is empty, skip to next ...", action="jobmonitor")	
			continue

		job_pids.append(job_pid)

	# - Query Slurm job status
	logger.info("#%d/%d Slurm jobs to be queried for status ..." % (len(job_pids), len(job_objs)), action="jobmonitor")
	
	try:
		resdict= jobmgr_slurm.get_job_statuses(job_pids)
	except Exception as e:
		logger.warn("Failed to retrieve Slurm job statuses (err=%s)" % (str(e)), action="jobmonitor")
		return -1

	if not resdict or resdict is None:
		logger.warn("Empty or None reply returned from Slurm client get_job_statuses(), cannot update job!", action="jobmonitor")
		return -1

	# - Loop over jobs and update their status
	for job_obj in job_objs:
		job_id= job_obj['job_id']
		job_pid= str(job_obj['pid'])

		# - Search status data with this pid
		if job_pid not in resdict:
			logger.warn("Cannot find Slurm job pid %s in dictionary of job status data, skip to next job ..." % job_pid, action="jobmonitor")
			continue

		res= resdict[job_pid]
		if not res or res is None:
			logger.warn("Empty or None job status dict for job pid %s, cannot update job, skip to next job ..." % job_pid, action="jobmonitor")
			continue

		# - Update status in DB and perform actions on completed jobs
		if update_slurm_job(job_obj, res, job_collection)<0:
			logger.warn("Failed to update Slurm job (id=%s, pid=%s), skip to next..." % (job_id, job_pid), action="jobmonitor")
			continue


	return 0
	

def monitor_slurm_job(job_obj, job_collection):
	""" Monitor and update job status in DB """
	
	# - Extract field
	if not job_obj or job_obj is None:
		logger.warn("Given job obj is None or empty!", action="jobmonitor")	
		return -1		
	job_id= job_obj['job_id']
	job_pid= str(job_obj['pid'])

	if job_pid=="":
		logger.warn("Given job pid is empty, cannot retrieve job status from Slurm cluster!", action="jobmonitor")	
		return -1

	job_dir_name= 'job_' + job_id
	tar_filename= 'job_' + job_id + '.tar.gz'
	job_top_dir= ''
	job_dir= ''
	tar_file= ''
	job_dir_existing= False
	tar_file_existing= False
	if 'job_top_dir' in job_obj:
		job_top_dir= job_obj['job_top_dir']
		job_dir= os.path.join(job_top_dir,job_dir_name)
		tar_file= os.path.join(job_dir,tar_filename)
		job_dir_existing= os.path.isdir(job_dir)
		tar_file_existing= os.path.isfile(tar_file)

	# - Check job collection
	if job_collection is None:
		logger.warn("Given mongo job collection is None!", action="jobmonitor")
		return -1

	# - Check Slurm client instance
	if jobmgr_slurm is None:
		logger.warn("Slurm client is None!", action="jobmonitor")
		return -1

	# - Get Slurm job status
	try:
		res= jobmgr_slurm.get_job_status(job_pid)
	except Exception as e:
		logger.warn("Failed to retrieve job %s (pid=%s) status (err=%s)" % (job_id, job_pid, str(e)), action="jobmonitor")
		return -1

	# - Check result
	if not res:
		logger.warn("Empty dict returned from Slurm client get_job_status(), cannot update job!", action="jobmonitor")
		return -1
		
	state= res['state']
	status= res['status']
	elapsed_time= res['elapsed_time']
	exit_code= res['exit_code']

	# - Create tar file with job output if job completed
	if state=='SUCCESS' or state=='FAILURE':
		if job_dir_existing and tar_file!="":
			if tar_file_existing:
				logger.info("Job %s output tar file %s already existing, won't create it again ..." % (job_id, tar_file), action="jobmonitor")
			else:
				logger.info("Creating a tar file %s with job output data ..." % tar_file, action="jobmonitor")
				utils.make_tar(tar_file, job_dir)
		else:
			logger.warn("Won't create output data tar file %s as job output directory %s not found ..." % (tar_file, job_dir), action="jobmonitor")

			
	# - Update job status
	try:
		logger.info("Updating job %s state to %s (status=%s) ..." % (job_id, state, status), action="jobmonitor")
		job_collection.update_one({'job_id':job_id},{'$set':{'state':state,'status':status,'exit_code':exit_code,'elapsed_time':elapsed_time}},upsert=False)
	except Exception as e:
		errmsg= 'Exception caught when updating job ' + str(job_id) + ' in DB (err=' + str(e) + ')!'
		logger.warn(errmsg, action="jobmonitor")
		return -1

	return 0



def update_slurm_job(job_obj, res, job_collection):
	""" Update slurm job status """

	# - Check result
	if not res or res is None:
		logger.warn("Empty or None job status dict given, cannot update job!", action="jobmonitor")
		return -1
	
	# - Get fields
	job_id= job_obj['job_id']
	job_pid= str(job_obj['pid'])

	job_dir_name= 'job_' + job_id
	tar_filename= 'job_' + job_id + '.tar.gz'
	job_top_dir= ''
	job_dir= ''
	tar_file= ''
	job_dir_existing= False
	tar_file_existing= False
	if 'job_top_dir' in job_obj:
		job_top_dir= job_obj['job_top_dir']
		job_dir= os.path.join(job_top_dir,job_dir_name)
		tar_file= os.path.join(job_dir,tar_filename)
		job_dir_existing= os.path.isdir(job_dir)
		tar_file_existing= os.path.isfile(tar_file)

	state= res['state']
	status= res['status']
	elapsed_time= res['elapsed_time']
	exit_code= res['exit_code']

	# - Create tar file with job output if job completed
	if state=='SUCCESS' or state=='FAILURE':
		if job_dir_existing and tar_file!="":
			if tar_file_existing:
				logger.info("Job %s output tar file %s already existing, won't create it again ..." % (job_id, tar_file), action="jobmonitor")
			else:
				logger.info("Creating a tar file %s with job output data ..." % tar_file, action="jobmonitor")
				utils.make_tar(tar_file, job_dir)
		else:
			logger.warn("Won't create output data tar file %s as job output directory %s not found ..." % (tar_file, job_dir), action="jobmonitor")

	# - Update job status
	try:
		logger.info("Updating job %s state to %s (status=%s) ..." % (job_id, state, status), action="jobmonitor")
		job_collection.update_one({'job_id':job_id},{'$set':{'state':state,'status':status,'exit_code':exit_code,'elapsed_time':elapsed_time}},upsert=False)
	except Exception as e:
		errmsg= 'Exception caught when updating job ' + str(job_id) + ' in DB (err=' + str(e) + ')!'
		logger.warn(errmsg, action="jobmonitor")
		return -1

	return 0


