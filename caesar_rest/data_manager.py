#! /usr/bin/env python

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
import uuid

from threading import RLock
lock = RLock()

try:
	FileNotFoundError  # python3
except NameError:
	FileNotFoundError = IOError # python2


## Get logger
logger = logging.getLogger(__name__)


##############################
#   DATA MANAGER CLASS
##############################

class DataManager(object):
	""" Data manager class """

	def __init__(self,rootdir):
		""" Return a data manager class """
	
		logger.info("Initializing DataManager class (resetting dict)...")
		self.data_root= rootdir
		self.data_dict= {}


	def register_data(self):
		""" Register data uuid of all files in app data directory """
		
		# - Recursively run through all files in app data dir 
		#   and generate uuid for all of them
		self.data_dict= {}
		path= self.data_root
		logger.info("Recursively traverse app data dir %s and generate data id dictionary ..." % path)		
		
		for filename in os.listdir(path):
			filename_fullpath= os.path.join(path, filename)
			if os.path.isfile(filename_fullpath):
				file_uuid= os.path.splitext(filename)[0]
				self.data_dict[file_uuid]= filename_fullpath

		
	def register_file(self,filename):
		""" Add file to dictionary """

		# - Check if file exist
		if not os.path.isfile(filename):
			logger.error('Will not register a file (%s) that is not existing on filesystem!' % filename)
			return -1
			
		# - Extract basefilename and uuid
		filename_base= os.path.basename(filename)
		filename_base_noext, file_ext = os.path.splitext(filename_base)
		file_uuid= filename_base_noext

		# - Add to dictionary
		with lock:
			if file_uuid not in self.data_dict:
				self.data_dict[file_uuid]= filename
				logger.info("Added file %s to dictionary with uuid=%s ..." % (filename,file_uuid))
				logger.info("curr data dict=%s" % str(self.data_dict))

		return 0

	def get_filepath(self,uuid):
		""" Retrieve filepath from uuid """
		
		#print("self.data_dict")
		#print(self.data_dict)

		registered= uuid in self.data_dict
		if not registered:
			return ''

		return self.data_dict[uuid]

	def get_file_ids(self):
		""" Return all registered file ids as a list """		
		return list(self.data_dict.keys())
		
