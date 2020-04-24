#!/usr/bin/env python

from __future__ import print_function

############################################################
#              MODULE IMPORTS
############################################################
# - Standard modules
import os
import sys
import json
import time
import datetime
import numpy as np
import argparse

# - caesar_rest modules
import caesar_rest
from caesar_rest import __version__, __date__
from caesar_rest import logger
from caesar_rest.config import Config
from caesar_rest.data_manager import DataManager
from caesar_rest.job_configurator import JobConfigurator
from caesar_rest.app import create_app
#from caesar_rest.app import app 



#### GET SCRIPT ARGS ####
def str2bool(v):
	if v.lower() in ('yes', 'true', 't', 'y', '1'):
		return True
	elif v.lower() in ('no', 'false', 'f', 'n', '0'):
		return False
	else:
		raise argparse.ArgumentTypeError('Boolean value expected.')

###########################
##     ARGS
###########################
def get_args():
	"""This function parses and return arguments passed in"""
	parser = argparse.ArgumentParser(description="Parse args.")

	# - Specify cmd options
	parser.add_argument('-datadir','--datadir', dest='datadir', default='/opt/caesar-rest/data', required=False, type=str, help='Directory where to store uploaded data') 
	parser.add_argument('-jobdir','--jobdir', dest='jobdir', default='/opt/caesar-rest/jobs', required=False, type=str, help='Directory where to store jobs') 
	parser.add_argument('--debug', dest='debug', action='store_true')	
	parser.set_defaults(debug=True)	


	args = parser.parse_args()	

	return args


#===========================
#==   PARSE ARGS
#===========================
logger.info("Parsing cmd line arguments ...")
try:
	args= get_args()
except Exception as ex:
	logger.error("Failed to get and parse options (err=%s)",str(ex))
	sys.exit(1)

# - Input filelist
datadir= args.datadir
jobdir= args.jobdir
debug= args.debug

#===========================
#==   PARSE ARGS
#===========================
logger.info("Parsing cmd line arguments ...")
try:
	args= get_args()
except Exception as ex:
	logger.error("Failed to get and parse options (err=%s)",str(ex))
	sys.exit(1)

# - Input filelist
datadir= args.datadir
jobdir= args.jobdir
debug= args.debug

#===============================
#==   INIT
#===============================
# - Create config class
logger.info("Creating app configuration ...")
config= Config()
config.UPLOAD_FOLDER= datadir
config.JOB_DIR= jobdir

# - Create data manager	
logger.info("Creating data manager ...")
datamgr= DataManager(rootdir=config.UPLOAD_FOLDER)

# - Create job configurator
logger.info("Creating job configurator ...")
jobcfg= JobConfigurator()

#===============================
#==   CREATE APP
#===============================
logger.info("Creating and configuring app ...")
app= create_app(config,datamgr,jobcfg)



###################
##   MAIN EXEC   ##
###################
if __name__ == "__main__":
	
	#===============================
	#==   RUN APP
	#===============================
	logger.info("Running app ...")
	app.run(debug=debug)

	sys.exit(0)
