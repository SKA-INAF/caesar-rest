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

# Import caesare rest modules
from caesar_rest import oidc
from caesar_rest import mongo
from caesar_rest import utils
from caesar_rest.base_app_configurator import AppConfigurator
from caesar_rest.base_app_configurator import Option, ValueOption, EnumValueOption

# Get logger
from caesar_rest import logger

##########################################
#   ViT CLASSIFIER APP CONFIGURATOR
##########################################

class ViTClassifierAppConfigurator(AppConfigurator):
	""" Class to configure ViT image classifier application """

	def __init__(self):
		""" Return aapp configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'run_classifier.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			# == MODEL OPTIONS ==
			'model' : EnumValueOption(
				name='model',
				value='',
				value_type=str, 
				description='Classifier model to be used',
				category='MODEL',
				default_value='smorphclass_multilabel',
				allowed_values=['smorphclass_multilabel']
			),

			# == PRE-PROCESSING OPTIONS ==
			'zscale' : Option(
				name='zscale', 
				description='Apply z-scale transform with given contrast', 
				category='PREPROCESSING'
			),
			'zscale-contrast' : ValueOption(
				name='zscale-contrast',
				value='',
				value_type=float, 
				description='zscale contrast applied to all channels',
				category='PREPROCESSING',
				default_value=0.25
			),
			
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
			
		
		} ## close valid options
		
		
		# - Define option value transformers
		self.option_value_transformer= {
		
		
		} 
		
		# - Fill some default cmd args
		logger.debug("Adding some options by default ...", action="submitjob")
		self.cmd_args.append("--run")
		
	def set_data_input_option_value(self):
		""" Set app input option value """

		input_opt= "".join("--inputfile=%s" % self.data_inputs)
		self.cmd_args.append(input_opt)
		
