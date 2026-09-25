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
#   FEAT EXTRACTOR APP CONFIGURATOR
##########################################
MODEL_CONTAINER_VARIANTS = {
	"simclr_radio": "tf",
	"dinov2": "torch",
	"dinov3": "torch",
	"dinov2_legacy": "torch",
	"siglip": "torch",
	"siglip2": "torch",
}

class FeatExtractorAppConfigurator(AppConfigurator):
	""" Class to configure feature extractor application """

	def __init__(self, app_name="fextractor"):
		""" Return app configurator class """
		AppConfigurator.__init__(self, app_name=app_name)

		# - Define cmd name
		self.cmd= 'run_fextractor.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Describe app
		self.description = (
			"Extract a data representation (i.e. features/embeddings) from input data using pretrained foundational models (see option --model). Currently supported input data modalities are: \n"
			"* images \n"
		)
		
		self.tool_categories= ["image"]
		
		self.input_requirements = {
			"supported_formats": ["fits", "png", "jpg", "json"],
			"expected_data": "Astronomical image (fits/png/jpg); Datalist (json) containing image list",
			"notes": [
				"WRITE ME"
			]
		}
		
		self.limitations = [
			"TBD",
			"TBD"
		]
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			# == MODEL OPTIONS ==
			'model' : EnumValueOption(
				name='model',
				value='',
				value_type=str, 
				description='Feature extraction model to be used',
				category='MODEL',
				default_value='simclr_radio',
				allowed_values=['simclr_radio','dinov2','dinov3','dinov2_legacy','siglip','siglip2']
			),

			# == PRE-PROCESSING OPTIONS ==
			"preproc-profile": EnumValueOption(
				name="preproc-profile",
				value="",
				value_type=str,
				description=(
					"Image preprocessing profile. If omitted, the default profile "
					"associated with the selected model is used."
				),
				category="PREPROCESSING",
				default_value="",
				allowed_values=["default", "simclr_radio"]
			),
			'norm-min' : ValueOption(
				name='norm-min',
				value='',
				value_type=float, 
				description='Normalization min value (default=0)',
				category='PREPROCESSING',
				default_value=0.0,
				min_value=-1.0,
				max_value=0.0
			),
			'norm-max' : ValueOption(
				name='norm-max',
				value='',
				value_type=float, 
				description='Normalization max value (default=1)',
				category='PREPROCESSING',
				default_value=1.0,
				min_value=1.0,
				max_value=255.0
			),
			'imgsize' : ValueOption(
				name='imgsize',
				value='',
				value_type=int,
				description=(
					'Model input image size in pixels. '
					'If omitted, the selected model default is used.'
				),
				category='PREPROCESSING',
				default_value='',
				min_value=16,
				max_value=1024
			),
			'nchannels' : ValueOption(
				name='nchannels',
				value='',
				value_type=int,
				description=(
					'Number of model input channels. '
					'If omitted, the selected model default is used.'
				),
				category='PREPROCESSING',
				default_value='',
				min_value=1,
				max_value=1000
			),
			'clipdata' : Option(
				name='clipdata', 
				description='Clip image pixel value in range [mean-5*stddev, mean+30*stddev]', 
				category='PREPROCESSING',
				default_value=False
			),
			'zscale' : Option(
				name='zscale',
				description=(
					'Enable or disable z-scale stretching. '
					'If omitted, the preprocessing profile default is used.'
				),
				category='PREPROCESSING',
				default_value=None
			),
			'zscale-contrast' : ValueOption(
				name='zscale-contrast',
				value='',
				value_type=float, 
				description='zscale contrast value applied to all channels',
				category='PREPROCESSING',
				default_value=0.25,
				min_value=0.0,
				max_value=1.0,
			),
			'set-zero-to-min' : Option(
				name='set-zero-to-min',
				description=(
					'Replace zero/blank/non-finite pixels with the minimum '
					'valid non-zero image value.'
				),
				category='PREPROCESSING',
				default_value=False
			),
			
			# == SAVE OPTIONS ==
			'outfile' : ValueOption(
				name='outfile',
				value='',
				value_type=str, 
				description='Output filename (.json) containing embedding/feature data extracted',
				category='SAVE',
				default_value='fextractor_results.json'
			),
			
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
		
		} ## close options
		
		
		# - Define dictionary with job outputs produced
		self.job_outputs= {
		
		}
		
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
		
		
	def validate(self, job_options, data_inputs):
		"""Validate fextractor inputs and resolve the runtime container."""

		# - Validate options
		valid = AppConfigurator.validate(
			self,
			job_options,
			data_inputs,
		)

		if not valid:
			return False

		# - Convert CAESAR boolean zscale=False to the negative
		#   command-line option expected by run_fextractor.sh.
		if "zscale" in self.job_options:
			zscale = self.job_options["zscale"]

			if zscale is False:
				self.cmd_args.append("--no-zscale")

		# - Resolve container variant
		model = self.job_options.get(
			"model",
			"simclr_radio",
		)

		if model not in MODEL_CONTAINER_VARIANTS:
			self.validation_status = (
				"Cannot determine container variant for model '%s'" % model
			)
			logger.warning(
				self.validation_status,
				action="submitjob",
			)
			return False

		self.run_options["container_variant"] = (
			MODEL_CONTAINER_VARIANTS[model]
		)

		return True	
		
