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
def accounter_task(self):
	""" Accounter task """

	logger.info("Executing accounter task ...")
	
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

	# - Init DB data structure
	logger.info("Creating data file object ...")
	now= datetime.datetime.utcnow()
	#account_data_list= []
	#_data= {
	#	"datasize": 0,
	#	"jobsize": 0,
	#}
	account_data= {}

	#collection_name= username + '.files'
		

	# - Traverse data directory and get users info
	users= [name for name in os.listdir(JOB_DIR) if os.path.isdir(os.path.join(JOB_DIR,name))]
	print("users")
	print(users)
	print("JOB_DIR")
	print(JOB_DIR)
	if users:
		logger.info("Found these users under job dir %s " % JOB_DIR)
		print(users)

		for user in users:
			userdir= os.path.join(JOB_DIR,user)
			dirsize= utils.get_dir_size(userdir)
			logger.info("User %s data dir size=%f" % (userdir,dirsize))

			if user in account_data:
				account_data[user]["jobsize"]= dirsize
			else:	
				account_data[user]= {}
				account_data[user]["timestamp"]= now
				account_data[user]["jobsize"]= dirsize
				
	
	# - Traverse job directory and get users info
	users= [name for name in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR,name))]
	if users:
		logger.info("Found these users under data dir %s " % DATA_DIR)
		print(users)

		for user in users:
			userdir= os.path.join(DATA_DIR,user)
			dirsize= utils.get_dir_size(userdir)
			logger.info("User %s job dir size=%f" % (userdir,dirsize))

			if user in account_data:
				account_data[user]["datasize"]= dirsize
			else:	
				account_data[user]= {}
				account_data[user]["timestamp"]= now
				account_data[user]["datasize"]= dirsize
	
	# - Query job DB and derive job information for all users
	logger.info("Query job DB and compute job stats for all users ...")

	for username in account_data:
		collection_name= username + '.jobs'
		job_list= []

		try:
			job_collection= client[DB_NAME][collection_name]
			job_cursor= job_collection.find({})
			job_list = list(job_cursor)

		except Exception as e:
			errmsg= 'Failed to get jobs from DB for user ' + username + ' (err=' + str(e) + ')'
			logger.error(errmsg)
			continue
		
		# - Compute some job stats
		n_jobs= len(job_list)
		n_jobs_pending= 0
		n_jobs_completed= 0
		n_jobs_failed= 0
		n_jobs_aborted= 0
		n_jobs_running= 0
		n_jobs_unknown= 0
		job_runtime= 0

		for job in job_list:
			#print("job")
			#print(job)
			job_state= 'UNKNOWN'
			job_elapsed_time= 0.
			if "state" in job:
				job_state= job["state"]
			if "elapsed_time" in job:
				job_elapsed_time= float(job["elapsed_time"])
			job_runtime+= job_elapsed_time
			if job_state=="SUCCESS":
				n_jobs_completed+= 1
			elif job_state=="FAILURE":
				n_jobs_failed+= 1
			elif job_state=="ABORTED":
				n_jobs_aborted+= 1
			elif job_state=="RUNNING" or job_state=="STARTED":
				n_jobs_running+= 1
			elif job_state=="PENDING":
				n_jobs_pending+= 1
			else:
				n_jobs_unknown+= 1

		# - Update account data with job stats
		account_data[username]["job_runtime"]= job_runtime
		account_data[username]["njobs"]= n_jobs
		account_data[username]["njobs_completed"]= n_jobs_completed
		account_data[username]["njobs_failed"]= n_jobs_failed
		account_data[username]["njobs_aborted"]= n_jobs_aborted
		account_data[username]["njobs_pending"]= n_jobs_pending
		account_data[username]["njobs_running"]= n_jobs_running
		account_data[username]["njobs_unknown"]= n_jobs_unknown
		
		
	print("account_data")
	print(account_data)

	# - Dump info to DB
	logger.info("Dumping into to DB ...")
	for username in account_data:
		data= account_data[username]
		collection_name= username + '.accounting'

		try:
			coll= client[DB_NAME][collection_name]
			item= coll.find_one()
			if item is None:
				coll.insert_one(data)
			else:
				coll.update_one({'_id':item['_id']},{'$set':data},upsert=False)
		except Exception as e:
			errmsg= 'Exception caught when updating account data for user '+  username + ' in DB (err=' + str(e) + ')!'
			logger.error(errmsg)
			continue

