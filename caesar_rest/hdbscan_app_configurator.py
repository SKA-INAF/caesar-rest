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
#   HDBSCAN APP CONFIGURATOR
##########################################

class HDBSCANAppConfigurator(AppConfigurator):
	""" Class to configure HDBSCAN application """

	def __init__(self):
		""" Return app configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'run_outlier_finder.sh'
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
			'selcols' : ValueOption(
				name='selcols',
				value='',
				value_type=str, 
				description='Data column ids to be selected from input data, separated by commas (default=all columns)',
				category='INPUT',
				default_value=''
			),
		
			# == HDBSCAN OPTIONS ==
			'min-cluster-size' : ValueOption(
				name='min-cluster-size',
				value='',
				value_type=int, 
				description='Minimum cluster size for HDBSCAN clustering (default=5)',
				category='PROCESSING',
				default_value=5,
				min_value=1,
				max_value=10000
			),
			'min-samples' : ValueOption(
				name='min-samples',
				value='',
				value_type=int, 
				description='Minimum cluster sample parameter for HDBSCAN clustering. <0 means setting it to None, which means equal to min_cluster_size (default=-1)',
				category='PROCESSING',
				default_value=-1,
				min_value=-1,
				max_value=10000
			),
			'cluster-selection-epsilon' : ValueOption(
				name='cluster-selection-epsilon',
				value='',
				value_type=float, 
				description='A distance threshold. Clusters below this value will be merged (default=0)',
				category='PROCESSING',
				default_value=0.0,
				min_value=0.0,
				max_value=10000.
			),
   		
			# == PRE-PROCESSING OPTIONS ==
			'normalize' : Option(
				name='normalize_minmax', 
				description='Normalize each channel in range', 
				category='PREPROCESSING'
			),
			'reduce-dim' : Option(
				name='reduce-dim', 
				description='Reduce feature data dimensionality before applying the clustering', 
				category='PREPROCESSING'
			),
			'reduce-dim-method' : ValueOption(
				name='reduce-dim-method',
				value='',
				value_type=str, 
				description='Dimensionality reduction method {pca} (default=pca)',
				category='INPUT',
				default_value='pca'
			),
			'pca-ncomps' : ValueOption(
				name='pca-ncomps',
				value='',
				value_type=int, 
				description='Number of PCA components to be used (-1=retain all cumulating a variance above threshold) (default=-1)',
				category='PROCESSING',
				default_value=-1,
				min_value=-1,
				max_value=10000
			),
			'pca-varthr' : ValueOption(
				name='pca-varthr',
				value='',
				value_type=float, 
				description='Cumulative variance threshold used to retain PCA components (default=0.9)',
				category='PROCESSING',
				default_value=0.9,
				min_value=0.0,
				max_value=1.0
			),
			
			# == SAVE OPTIONS ==
			'no-save-ascii' : Option(
				name='no-save-ascii', 
				description='Do not save output in ascii format', 
				category='OUTPUT'
			),
			'no-save-json' : Option(
				name='no-save-json', 
				description='Do not save output in json format', 
				category='OUTPUT'
			),
			'no-save-model' : Option(
				name='no-save-model', 
				description='Do not save model', 
				category='OUTPUT'
			),
			'no-save-features' : Option(
				name='no-save-features', 
				description='Do not save features in output files', 
				category='OUTPUT'
			),
			'outfile' : ValueOption(
				name='outfile',
				value='',
				value_type=str, 
				description='Name of output file in ascii format (default=outlier_data)',
				category='OUTPUT',
				default_value='outlier_data'
			),
			
			'outfile-json' : ValueOption(
				name='outfile-json',
				value='',
				value_type=str, 
				description='Name of output file in json format (default=outlier_data.json)',
				category='OUTPUT',
				default_value='outlier_data.json'
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
		
