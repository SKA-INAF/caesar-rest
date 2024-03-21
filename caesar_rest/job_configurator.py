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
import subprocess
import json
import ast
import yaml

# Import flask modules
from flask import current_app, g

# Import caesare rest momdules
from caesar_rest import oidc
from caesar_rest import mongo
from caesar_rest import utils
from caesar_rest.base_app_configurator import AppConfigurator
from caesar_rest.caesar_app_configurator import CaesarAppConfigurator
from caesar_rest.mrcnn_app_configurator import MaskRCNNAppConfigurator
from caesar_rest.aegean_app_configurator import AegeanAppConfigurator
from caesar_rest.cutex_app_configurator import CutexAppConfigurator
from caesar_rest.cnn_classifier_app_configurator import CNNClassifierAppConfigurator

# Get logger
from caesar_rest import logger

##############################
#   JOB CONFIGURATOR
##############################
class JobConfigurator(object):
	""" Class to configure job command """

	def __init__(self):
		""" Return a job configurator class """

		self.app_configurators= {
			'caesar': CaesarAppConfigurator,
			'mrcnn': MaskRCNNAppConfigurator,
			'aegean': AegeanAppConfigurator,
			'cutex': CutexAppConfigurator,
			'cnn_classifier': CNNClassifierAppConfigurator
		}
		
		
	def validate(self, app_name, job_inputs, data_inputs):
		""" Validate job inputs """

		# - Validate if job inputs are valid for app
		#   Delegate validation to app configurator
		if app_name not in self.app_configurators:
			msg= 'App ' + app_name + ' not known or supported'
			logger.warn(msg, action="submitjob")
			return (None,None,msg,None)

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()
		
		status= configurator.validate(job_inputs, data_inputs)
		if not status:
			status_msg= configurator.validation_status
			logger.warn("Given inputs for app %s failed to be validated!" % app_name, action="submitjob")
			return (None,None,status_msg,None)

		# - Set app cmd & cmd args
		cmd= configurator.cmd
		cmd_args= configurator.cmd_args
		if configurator.cmd_mode!="":
			cmd_args.append(configurator.cmd_mode)
		status_msg= configurator.validation_status
		run_opts= configurator.run_options		

		return (cmd,cmd_args,status_msg,run_opts)

	def get_app_description(self,app_name):
		""" Return a json dict describing given app """
		
		# - Check app name if found
		if app_name not in self.app_configurators:
			msg= 'App ' + app_name + ' not known or supported'
			logger.warn(msg, action="submitjob")
			return None

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()

		# - Get description
		d= configurator.describe_dict()	

		return d

	def get_app_names(self):
		""" Return app names """
		
		d= {}
		app_names= []
		for app_name in self.app_configurators:
			app_names.append(app_name)
		d.update({'apps':app_names})

		#return json.loads(json.dumps(d))
		return d


	def has_batch_processing_support(self,app_name):
		""" Check if given app supports batch processing """

		# - Check app name if found
		if app_name not in self.app_configurators:
			msg= 'App ' + app_name + ' not known or supported'
			logger.warn(msg, action="submitjob")
			return None

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()

		# - Get flag
		flag= configurator.batch_processing_support

		return flag


