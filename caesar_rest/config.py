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

##############################
#   APP CONFIG CLASS
##############################

class Config(object):
	""" Class holding configuration options for Flask app """

	# - Flask Options
	DEBUG = False
	TESTING = False
	SECRET_KEY= uuid.uuid4().hex
	UPLOAD_FOLDER= '/opt/data'
	MAX_CONTENT_LENGTH= 16 * 1024 * 1024 # 16 MB

	# - Celery options (do not change variable names)
	#broker_url= 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
	###broker_url= 'redis://localhost:6379'
	#result_backend= 'rpc://'
	###result_backend= 'redis://localhost:6379'
	#imports = ('caesar_rest.workers',)
	
	# - Additional options
	UPLOAD_ALLOWED_FILE_FORMATS= set(['png', 'jpg', 'jpeg', 'gif', 'fits'])
