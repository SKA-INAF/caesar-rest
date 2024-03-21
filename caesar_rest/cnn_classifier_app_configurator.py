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
#   CNN CLASSIFIER APP CONFIGURATOR
##########################################

class CNNClassifierAppConfigurator(AppConfigurator):
	""" Class to configure CNN image classifier application """

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
				default_value='smorphclass',
				allowed_values=['smorphclass','sclass-radio_3.4um-4.6um-12um-22um']
			),

			# == PRE-PROCESSING OPTIONS ==
			'imgsize' : ValueOption(
				name='imgsize',
				value='',
				value_type=int, 
				description='Image resize in pixels (default=64)',
				category='PREPROCESSING',
				default_value=64,
				min_value=16,
				max_value=1024
			),
			'normalize_minmax' : Option(
				name='normalize_minmax', 
				description='Normalize each channel in range', 
				category='OUTPUT'
			),
			'norm_min' : ValueOption(
				name='norm_min',
				value='',
				value_type=float, 
				description='Normalization min value (default=0)',
				category='PREPROCESSING',
				default_value=0.0,
				min_value=-1.0,
				max_value=0.0
			),
			'norm_max' : ValueOption(
				name='norm_max',
				value='',
				value_type=float, 
				description='Normalization max value (default=1)',
				category='PREPROCESSING',
				default_value=1.0,
				min_value=1.0,
				max_value=255.0
			),
			'scale_to_abs_max' : Option(
				name='scale_to_abs_max', 
				description='Scale to global max across all channels', 
				category='PREPROCESSING'
			),
			'scale_to_max' : Option(
				name='scale_to_max', 
				description='Scale to max not to min-max range', 
				category='PREPROCESSING'
			),
			'zscale_stretch' : Option(
				name='zscale_stretch', 
				description='Apply z-scale transform to each channel with given contrasts', 
				category='PREPROCESSING'
			),
			'zscale_contrasts' : ValueOption(
				name='zscale_contrasts',
				value='',
				value_type=str, 
				description='zscale contrasts applied to all channels, separated by commas',
				category='PREPROCESSING',
				default_value='0.25'
			),
			'clip_data' : Option(
				name='clip_data', 
				description='Apply sigma clipping to all channels', 
				category='PREPROCESSING'
			),
			'sigma_clip_low' : ValueOption(
				name='sigma_clip_low',
				value='',
				value_type=float, 
				description='Lower sigma threshold to be used for clipping pixels below (mean-sigma_low*stddev) (default=5)',
				category='PREPROCESSING',
				default_value=5.0
			),
			'sigma_clip_up' : ValueOption(
				name='sigma_clip_up',
				value='',
				value_type=float, 
				description='Upper sigma threshold to be used for clipping pixels above (mean+sigma_up*stddev) (default=30)',
				category='PREPROCESSING',
				default_value=30.0
			),
			'clip_chid' : ValueOption(
				name='clip_chid',
				value='',
				value_type=int, 
				description='Channel to clip data (-1=all) (default=-1)',
				category='PREPROCESSING',
				default_value=-1
			),
			'standardize' : Option(
				name='standardize', 
				description='Apply standardization to images', 
				category='PREPROCESSING'
			),
			'img_means' : ValueOption(
				name='img_means',
				value='',
				value_type=str, 
				description='Image means (separated by commas) to be used in standardization (default=0)',
				category='PREPROCESSING',
				default_value='0'
			),
			'img_sigmas' : ValueOption(
				name='img_sigmas',
				value='',
				value_type=str, 
				description='Image sigmas (separated by commas) to be used in standardization (default=1)',
				category='PREPROCESSING',
				default_value='1'
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
		
