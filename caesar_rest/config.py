#! /usr/bin/env python

##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import sys
import uuid

# Import module files
##from caesar_rest.data_manager import DataManager ## DEPRECATED
from caesar_rest.job_configurator import JobConfigurator

##############################
#   APP CONFIG CLASS
##############################

class Config(object):
	""" Class holding configuration options for Flask app """

	# - Flask Options
	DEBUG = False
	TESTING = False
	SECRET_KEY= uuid.uuid4().hex
	UPLOAD_FOLDER= '/opt/caesar-rest/data'
	MAX_CONTENT_LENGTH= 1000 * 1024 * 1024 # 16 MB

	# - Additional options
	JOB_DIR= '/opt/caesar-rest/jobs'
	UPLOAD_ALLOWED_FILE_FORMATS= set(['png', 'jpg', 'jpeg', 'gif', 'fits'])
	#APP_NAMES= set(['sfinder']) 
	JOB_MONITORING_PERIOD= 5 # in seconds

	JOB_SCHEDULER= 'celery' # Options are: {'celery','kubernetes','slurm'}

	# - KUBERNETES options
	# ...

	# - SLURM options
	USE_SLURM= False
	SLURM_QUEUE= 'normal'
	SLURM_USER= 'cirasa'	
	
	# - AAI options
	USE_AAI = False
	OIDC_CLIENT_SECRETS = 'config/client_secrets.json'
	OIDC_OPENID_REALM = 'neanias-development'
	OIDC_SCOPES = ['openid', 'email', 'profile']

	# - MONG DB options
	USE_MONGO = False
	MONGO_HOST= 'localhost'
	MONGO_PORT= 27017
	MONGO_DBNAME= 'caesardb' 
	MONGO_URI= 'mongodb://localhost:27017/caesardb'

	# - App options
	SFINDERNN_WEIGHTS= '/opt/caesar-rest/share/mrcnn_weights.h5'
