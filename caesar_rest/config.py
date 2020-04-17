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

	# - Options
	DEBUG = False
	TESTING = False
	SECRET_KEY= uuid.uuid4().hex
	UPLOAD_FOLDER= '/opt/data'
	MAX_CONTENT_LENGTH= 16 * 1024 * 1024 # 16 MB

	# - Helper classes
	def init():
		""" Initialize helper classes """

		datamgr= DataManager(rootdir=UPLOAD_FOLDER)
