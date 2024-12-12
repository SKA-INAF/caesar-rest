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
#   UMAP APP CONFIGURATOR
##########################################

class UMAPAppConfigurator(AppConfigurator):
	""" Class to configure UMAP application """

	def __init__(self):
		""" Return aapp configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'run_umap.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			# == INPUT OPTIONS ==
			'datalist-key' : ValueOption(
				name='datalist-key',
				value='',
				value_type=str, 
				description='Dictionary key name to be read in input datalist (default=data)',
				category='INPUT',
				default_value='data'
			),
		
			# == UMAP OPTIONS ==
			'nfeats' : ValueOption(
				name='nfeats',
				value='',
				value_type=int, 
				description='Encoded data dim in UMAP (default=2)',
				category='PREPROCESSING',
				default_value=2,
				min_value=2,
				max_value=512
			),
			'mindist' : ValueOption(
				name='mindist',
				value='',
				value_type=float, 
				description=' Min dist UMAP parameter (default=0.1)',
				category='PREPROCESSING',
				default_value=0.1,
				min_value=0.0,
				max_value=1.0
			),
			'nneighbors' : ValueOption(
				name='nneighbors',
				value='',
				value_type=int, 
				description='N neighbors UMAP parameter (default=15)',
				category='PREPROCESSING',
				default_value=15,
				min_value=1,
				max_value=10000
			),

			# == PRE-PROCESSING OPTIONS ==
			'normalize' : Option(
				name='normalize_minmax', 
				description='Normalize each channel in range', 
				category='PREPROCESSING'
			),
			
			# == SAVE OPTIONS ==
			'no-save-ascii' : Option(
				name='no-save-ascii', 
				description='Do not save output in ascii format', 
				category='PREPROCESSING'
			),
			'no-save-json' : Option(
				name='no-save-json', 
				description='Do not save output in json format', 
				category='PREPROCESSING'
			),
			'outfile-sup' : ValueOption(
				name='outfile-sup',
				value='',
				value_type=str, 
				description='Name of UMAP encoded data output file for supervised run in ascii format (default=featdata_umap_sup.dat)',
				category='OUTPUT',
				default_value='featdata_umap_sup.dat'
			),
			'outfile-unsup' : ValueOption(
				name='outfile-unsup',
				value='',
				value_type=str, 
				description='Name of UMAP encoded data output file in ascii format (default=featdata_umap.dat)',
				category='OUTPUT',
				default_value='featdata_umap.dat'
			),
			'outfile-unsup-json' : ValueOption(
				name='outfile-unsup-json',
				value='',
				value_type=str, 
				description='Name of UMAP encoded data output file in json format (default=featdata_umap.json)',
				category='OUTPUT',
				default_value='featdata_umap.json'
			),
			
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
			'run-supervised' : Option(
				name='run-supervised', 
				description='Run UMAP also on labelled data alone (if available)',
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
		
