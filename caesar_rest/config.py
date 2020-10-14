#! /usr/bin/env python

##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import sys
import uuid

# Import module files
from caesar_rest.data_manager import DataManager
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
	
	# - AAI options
	USE_AAI = False
	OIDC_CLIENT_SECRETS = 'config/client_secrets.json'
	OIDC_OPENID_REALM = 'neanias-development'
	OIDC_SCOPES = ['openid', 'email', 'profile']
