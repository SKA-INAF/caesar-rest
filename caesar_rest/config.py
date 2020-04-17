#! /usr/bin/env python

import uuid

##############################
#   APP CONFIG CLASS
##############################

class Config(object):
	""" Class holding configuration options for Flask app """

	DEBUG = False
	TESTING = False
	SECRET_KEY= uuid.uuid4().hex
	UPLOAD_FOLDER= '/opt/data'
	MAX_CONTENT_LENGTH= 16 * 1024 * 1024 # 16 MB
