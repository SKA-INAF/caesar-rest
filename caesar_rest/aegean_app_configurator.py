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

#######################################
#   AEGEAN SFINDER APP CONFIGURATOR
#######################################

class AegeanAppConfigurator(AppConfigurator):
	""" Class to configure AEGEAN sfinder application """

	def __init__(self):
		""" Return aegean sfinder app configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'aegean_submitter.sh'
		self.cmd_args= []
		self.batch_processing_support= True

		# - Define dictionary with allowed options
		self.valid_options= {
			
			# == OUTPUT OPTIONS ==
			'save-bkgmap' : Option(
				name='save-bkgmap', 
				description='Save bkg map in output file', 
				category='OUTPUT'
			),
			'save-rmsmap' : Option(
				name='save-rmsmap', 
				description='Save rms map in output file', 
				category='OUTPUT'
			),

			# == BKG OPTIONS ==
			'bkgbox' : ValueOption(
				name='bkgbox',
				value='',
				value_type=int, 
				description='Box size in pixels used to compute local bkg (default: 5*grid if not given)',
				category='IMGBKG',
				default_value=100,
				min_value=5,
				max_value=10000
			),
			'bkggrid' : ValueOption(
				name='bkggrid',
				value='',
				value_type=int, 
				description='Grid size in pixels used to compute local bkg (default: ~4* beam size square if not given)',
				category='IMGBKG',
				default_value=20,
				min_value=5,
				max_value=1000
			),
			
			# == COMPACT SOURCE SEARCH OPTIONS ==
			'seedthr' : ValueOption(
				name='seedthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used in flood-fill algo',
				category='COMPACT-SOURCES',
				default_value=5,
				min_value=0,
				max_value=10000
			),
			'mergethr' : ValueOption(
				name='mergethr',
				value='',
				value_type=float, 
				description='Merge threshold (in nsigmas) used in flood-fill algo',
				category='COMPACT-SOURCES',
				default_value=2.6,
				min_value=0,
				max_value=10000
			),
			
			# == SOURCE FITTING OPTIONS ==
			'fit-maxcomponents' : ValueOption(
				name='fit-maxcomponents',
				value='',
				value_type=int, 
				description='Maximum number of components fitted in a blob',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=3,
				min_value=0,
				max_value=100
			),
			
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
			'ncores' : ValueOption(
				name='ncores',
				value='',
				value_type=int, 
				description='Number of cores to be used in BANE/aegean',
				category='RUN',
				default_value=1,
				min_value=1,
				max_value=100
			),
			
		} # close dict

		# - Define option value transformers
		self.option_value_transformer= {
			
		}

		# - Fill some default cmd args
		logger.debug("Adding some options by default ...", action="submitjob")
		self.cmd_args.append("--run")
		self.cmd_args.append("--save-summaryplot")
		self.cmd_args.append("--save-regions ")
		self.cmd_args.append("--save-catalog-to-json ")


	
	def set_data_input_option_value(self):
		""" Set app input option value """

		input_opt= "".join("--inputfile=%s" % self.data_inputs)
		self.cmd_args.append(input_opt)


	def transform_inputfile(self,file_uuid):
		""" Transform input file from uuid to actual path """		
	
		# - Get aai info
		username= 'anonymous'
		if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
			email= g.oidc_token_info['email']
			username= utils.sanitize_username(email)

		# - Inspect inputfile (expect it is a uuid, so convert to filename)
		logger.info("Finding inputfile uuid %s ..." % file_uuid, action="submitjob")
		collection_name= username + '.files'

		file_path= ''
		try:
			data_collection= mongo.db[collection_name]
			item= data_collection.find_one({'fileid': str(file_uuid)})
			if item and item is not None:
				file_path= item['filepath']
			else:
				logger.warn("File with uuid=%s not found in DB!" % file_uuid, action="submitjob")
				file_path= ''
		except Exception as e:
			logger.error("Exception (err=%s) catch when searching file in DB!" % str(e), action="submitjob")
			return ''
		
		if not file_path or file_path=='':
			logger.warn("inputfile uuid %s is empty or not found in the system!" % file_uuid, action="submitjob")
			return ''

		logger.info("inputfile uuid %s converted in %s ..." % (file_uuid,file_path), action="submitjob")

		return file_path
		
