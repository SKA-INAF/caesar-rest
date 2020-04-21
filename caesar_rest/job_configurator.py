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
from flask import current_app

# Get logger
logger = logging.getLogger(__name__)




##############################
#   JOB CONFIGURATOR
##############################
class JobConfigurator(object):
	""" Class to configure job command """

	def __init__(self):
		""" Return a job configurator class """

		self.app_configurators= {
			'sfinder': SFinderConfigurator
		}

		
	def validate(self,app_name,job_inputs):
		""" Validate job inputs """

		# - Validate if job inputs are valid for app
		#   Delegate validation to app configurator
		if app_name not in self.app_configurators:
			logger.warn("App %s not known or supported!" % app_name)
			return ()

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()

		#status= self.app_configurators[app_name].validate(job_inputs)
		status= configurator.validate(job_inputs)
		if status<0:
			logger.warn("Given inputs for app %s failed to be validated!" % app_name)
			return ()

		# - Set app cmd & cmd args
		cmd= configurator.cmd
		cmd_args= configurator.cmd_args
		
		return (cmd,cmd_args)



##############################
#   APP CONFIGURATOR
##############################
class Option(object):

	def __init__(self,name,mandatory=False):
		self.name= name
		self.mandatory= mandatory
		self.value_required= False
		self.value= ''
		self.value_type= bool

	def to_argopt(self):
		""" Convert option to cmdline format """
		
		if self.value_required:
			argopt= '--' + self.name + '=' + str(self.value)
		else:
			argopt= '--' + self.name

		return argopt


class ValueOption(Option):

	def __init__(self,name,value,value_type,mandatory=False):
		""" Return value option """
		Option.__init__(self,name,mandatory)
		self.value= value
		self.value_required= True
		self.value_type= value_type


class AppConfigurator(object):
	""" Class to define base app configurator """
  
	def __init__(self):
		""" Constructor"""

		self.job_inputs= ''
		self.cmd= ''
		self.cmd_args= []
		self.validation_status= ''
		self.valid_options= {}
		self.options= []

	def validate(self,job_inputs):
		""" Validate job input """

		logger.info("Validating given inputs ...")

		# - Check if job inputs are empty
		if not job_inputs:		
			self.validation_status= 'Empty job inputs given!'
			logger.warn(self.validation_status)
			return False

		# - Convert json string to dictionary
		print("type(job_inputs)")
		print(type(job_inputs))
		print(job_inputs)

		if not isinstance(job_inputs,dict):
			self.validation_status= 'Given job inputs data is not a dictionary!'
			logger.warn(self.validation_status)
			return False

		try:
			self.job_inputs= yaml.safe_load(json.dumps(job_inputs))

		except ValueError:
			self.validation_status= 'Failed to parse job inputs as json dictionary!'
			logger.warn(self.validation_status)
			return False

		print("type(self.job_inputs)")
		print(type(self.job_inputs))
		print(self.job_inputs)

		# - Validate options 
		valid= self.validate_options()
		print("--> %s args" % self.cmd)
		print(self.cmd_args)
		
		return valid


	def validate_options(self):
		""" Validate parsed options against valid expected options (provided in derived class) """

		# - Validate options
		for opt_name, option in self.valid_options.items():
			option_given= opt_name in self.job_inputs

			# - Check if mandatory option is given
			mandatory= option.mandatory
			if mandatory and not option_given:
				self.validation_status= ''.join(["Mandatory option ",opt_name," not present!"])
				logger.warn(self.validation_status)
				return False
	
			# - Skip if not given
			if not option_given:
				continue

			# - Check if required value
			value_required= option.value_required
			if value_required:
				# - Check for value type
				expected_val_type= option.value_type
				parsed_value= self.job_inputs[opt_name]
				parsed_value_type= type(parsed_value)
				if not isinstance(parsed_value,expected_val_type):
					self.validation_status= ''.join(["Option ",opt_name," expects a ",str(expected_val_type)," value type and not a ",str(parsed_value_type)," !"])
					logger.warn(self.validation_status)
					return False

				# - Add option
				value_option= ValueOption(opt_name,str(parsed_value),expected_val_type,mandatory)
				self.options.append(value_option)

				# - Convert to cmd arg format
				argopt= value_option.to_argopt()
				self.cmd_args.append(argopt)
			
			else: # No value required
				bool_option= Option(opt_name,mandatory)
				self.options.append(bool_option)

				# - Convert to cmd arg format
				argopt= bool_option.to_argopt()
				self.cmd_args.append(argopt)

		return True


##############################
#   SFINDER APP CONFIGURATOR
##############################

class SFinderConfigurator(AppConfigurator):
	""" Class to configure sfinder application """

	def __init__(self):
		""" Return sfinder configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'SFinderSubmitter.sh'
		self.cmd_args= []

		# - Define dictionary with allowed options
		self.valid_options= {
			# == INPUT OPTIONS ==
			'inputfile' : ValueOption('inputfile','',str,True),
			#'filelist' : ValueOption('filelist','',True),
		
			# == OUTPUT OPTIONS==		
			'save-inputmap' : Option('save-inputmap'),	
		}
	
			
	
	
