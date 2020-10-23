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
from caesar_rest import oidc
#from caesar_rest import db
from caesar_rest import mongo


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
	parser.add_argument('--aai', dest='aai', action='store_true')	
	parser.set_defaults(aai=False)	
	parser.add_argument('-secretfile','--secretfile', dest='secretfile', default='config/client_secrets.json', required=False, type=str, help='File (.json) with client credentials for AAI')
	parser.add_argument('-openid_realm','--openid_realm', dest='openid_realm', default='neanias-development', required=False, type=str, help='OpenID realm used in AAI (defaul=neanias-development)') 
	parser.add_argument('--ssl', dest='ssl', action='store_true')	
	parser.set_defaults(ssl=False)
	
	parser.add_argument('-sfindernn_weights','--sfindernn_weights', dest='sfindernn_weights', default='/opt/caesar-rest/share/mrcnn_weights.h5', required=False, type=str, help='File (.h5) with network weights used in sfindernn app')

	parser.add_argument('--db', dest='db', action='store_true')	
	parser.set_defaults(db=False)
	parser.add_argument('-dbhost','--dbhost', dest='dbhost', default='localhost', required=False, type=str, help='Host of MongoDB database (default=localhost)')
	parser.add_argument('-dbname','--dbname', dest='dbname', default='caesardb', required=False, type=str, help='Name of MongoDB database (default=caesardb)')

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
use_aai= args.aai
secret_file= args.secretfile
openid_realm= args.openid_realm
ssl= args.ssl
sfindernn_weights= args.sfindernn_weights
use_db= args.db
dbhost= 'mongodb://' + args.dbhost + '/' + args.dbname

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
config.USE_AAI= False
if use_aai and oidc is not None:
	config.USE_AAI= True
	config.SECRET_KEY= 'SomethingNotEntirelySecret'
	config.OIDC_CLIENT_SECRETS= secret_file
	config.OIDC_OPENID_REALM= openid_realm

#if use_db and db is not None:
if use_db and mongo is not None:
	config.MONGO_URI= dbhost
	config.USE_MONGO= True

	#config.MONGODB_SETTINGS= {
	#	'db': args.dbname,
  #  'host': args.dbhost,
  #  'port': 27017
	#}


config.SFINDERNN_WEIGHTS = sfindernn_weights

# - Create data manager	
logger.info("Creating data manager ...")
datamgr= DataManager(rootdir=config.UPLOAD_FOLDER)
datamgr.register_data()

# - Create job configurator
logger.info("Creating job configurator ...")
jobcfg= JobConfigurator()

#===============================
#==   CREATE APP
#===============================
logger.info("Creating and configuring app ...")
app= create_app(config,datamgr,jobcfg)

#===============================
#==   INIT OIDC TO APP
#===============================
# - Add Flask OIDC configuration
if use_aai and oidc is not None:
	logger.info("Initializing OIDC to app ...")
	try:
		oidc.init_app(app)
	except:
		logger.error("Failed to initialize OIDC to app!")
else:
	logger.info("Starting app without AAI ...")

#===============================
#==   INIT MONGO TO APP
#===============================
#if db is not None:
if mongo is not None:
	logger.info("Initializing MongoDB engine to app ...")
	try:
		#db.init_app(app)
		mongo.init_app(app)
	except:
		logger.error("Failed to initialize MongoDB to app!")
else:
	logger.info("Starting app without mongo backend ...")

###################
##   MAIN EXEC   ##
###################
if __name__ == "__main__":
	
	#===============================
	#==   RUN APP
	#===============================
	if ssl:
		logger.info("Running app on SSL ...")
		app.run(debug=debug, ssl_context='adhoc')
	else:
		logger.info("Running app ...")
		app.run(debug=debug)

	sys.exit(0)
