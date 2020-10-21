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
	
		self.data_root= rootdir
		self.data_dict= {}

	def register_data(self):
		""" Register data uuid of all files in app data directory """
		
		# - Recursively run through all files in app data dir 
		#   and generate uuid for all of them
		self.data_dict= {}
		logger.info("Recursively traverse app data dir %d and generate data id dictionary ...")		
		
		# ...
		# ...

	def register_file(self,filename):
		""" Add file to dictionary """

		# - Check if file exist
		if not os.path.isfile(filename):
			logger.error('Will not register a file that is not existing on filesystem!')
			return -1
			
		# - Extract basefilename and uuid
		filename_base= os.path.basename(filename)
		filename_base_noext, file_ext = os.path.splitext(filename_base)
		file_uuid= filename_base_noext

		# - Add to dictionary
		self.data_dict[file_uuid]= filename
		logger.info("Added file %s to dictionary with uuid=%s ..." % (filename,file_uuid))

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
		
