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
## from caesar_rest.data_manager import DataManager  ### DEPRECATED
from caesar_rest.job_configurator import JobConfigurator
from caesar_rest.app import create_app
from caesar_rest import oidc
from caesar_rest import mongo
from caesar_rest import celery


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
	parser.add_argument('-job_monitoring_period','--job_monitoring_period', dest='job_monitoring_period', default=5, required=False, type=int, help='Job monitoring poll period in seconds') 
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
	parser.add_argument('-dbport','--dbport', dest='dbport', default=27017, required=False, type=int, help='Port of MongoDB database (default=27017)')

	parser.add_argument('-result_backend_host','--result_backend_host', dest='result_backend_host', default='localhost', required=False, type=str, help='Host of Celery result backend (default=localhost)')
	parser.add_argument('-result_backend_port','--result_backend_port', dest='result_backend_port', default=6379, required=False, type=int, help='Port of Celery result backend (default=6379)')
	parser.add_argument('-result_backend_proto','--result_backend_proto', dest='result_backend_proto', default='redis', required=False, type=str, help='Celery result backend type (default=redis)')
	parser.add_argument('-result_backend_user','--result_backend_user', dest='result_backend_user', default='', required=False, type=str, help='Celery result backend username (default=empty)')
	parser.add_argument('-result_backend_pass','--result_backend_pass', dest='result_backend_pass', default='', required=False, type=str, help='Celery result backend password (default=empty)')
	parser.add_argument('-result_backend_dbname','--result_backend_dbname', dest='result_backend_dbname', default='0', required=False, type=str, help='Celery result backend database name (default=empty)')

	parser.add_argument('-broker_host','--broker_host', dest='broker_host', default='localhost', required=False, type=str, help='Host of Celery broker (default=localhost)')
	parser.add_argument('-broker_port','--broker_port', dest='broker_port', default=5672, required=False, type=int, help='Port of Celery broker (default=5672)')
	parser.add_argument('-broker_proto','--broker_proto', dest='broker_proto', default='amqp', required=False, type=str, help='Protocol of Celery broker (default=amqp)')
	parser.add_argument('-broker_user','--broker_user', dest='broker_user', default='guest', required=False, type=str, help='Username used in Celery broker (default=guest)')
	parser.add_argument('-broker_pass','--broker_pass', dest='broker_pass', default='guest', required=False, type=str, help='Password used in Celery broker (default=guest)')


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

# - Dir options
datadir= args.datadir
jobdir= args.jobdir
debug= args.debug

# - AAI options
use_aai= args.aai
secret_file= args.secretfile
openid_realm= args.openid_realm
ssl= args.ssl

# - App options
job_monitoring_period= args.job_monitoring_period
sfindernn_weights= args.sfindernn_weights

# - DB & celery result backend options
use_db= args.db
dbhost= 'mongodb://' + args.dbhost + ':' + str(args.dbport) + '/' + args.dbname
logger.info("Using dbhost: %s" % dbhost)

result_backend_host= args.result_backend_host
result_backend_port= args.result_backend_port
result_backend_proto= args.result_backend_proto
result_backend_user= args.result_backend_user
result_backend_pass= args.result_backend_pass
result_backend_dbname= args.result_backend_dbname

result_backend= ''
if result_backend_proto=='redis':	
	result_backend= result_backend_proto + '://' + result_backend_host + ':' + str(result_backend_port) + '/' + result_backend_dbname
elif result_backend_proto=='mongodb':
	result_backend= result_backend_proto + '://' + result_backend_host + ':' + str(result_backend_port) + '/' + result_backend_dbname
else:
	logger.error("Unsupported result backend (hint: supported are {redis,mongodb})!")
	sys.exit(1)
logger.info("Using result_backend: %s" % result_backend)


# - Celery broker options
broker_host= args.broker_host
broker_port= args.broker_port
broker_proto= args.broker_proto
broker_user= args.broker_user
broker_pass= args.broker_pass 
broker_url= broker_proto + '://' + broker_user + ':' + broker_pass + '@' + broker_host + ':' + str(broker_port) + '/'
logger.info("Using broker_url: %s" % broker_url)



#===============================
#==   INIT
#===============================
# - Create config class
logger.info("Creating app configuration ...")
config= Config()
config.UPLOAD_FOLDER= datadir
config.JOB_DIR= jobdir
config.USE_AAI= False
config.JOB_MONITORING_PERIOD= job_monitoring_period

if use_aai and oidc is not None:
	config.USE_AAI= True
	config.SECRET_KEY= 'SomethingNotEntirelySecret'
	config.OIDC_CLIENT_SECRETS= secret_file
	config.OIDC_OPENID_REALM= openid_realm
	config.OIDC_TOKEN_TYPE_HINT = 'access_token'


if use_db and mongo is not None:
	config.MONGO_HOST= args.dbhost
	config.MONGO_PORT= args.dbport
	config.MONGO_DBNAME= args.dbname
	config.MONGO_URI= dbhost
	config.USE_MONGO= True

config.SFINDERNN_WEIGHTS = sfindernn_weights

# - Create data manager (DEPRECATED BY MONGO)
##logger.info("Creating data manager ...")
##datamgr= DataManager(rootdir=config.UPLOAD_FOLDER)
##datamgr.register_data()

# - Create job configurator
logger.info("Creating job configurator ...")
jobcfg= JobConfigurator()

# - Update celery configs
logger.info("Updating celery configuration (broker_url=%s, result_backend=%s) ..." % (broker_url, result_backend))
celery.conf.result_backend= result_backend
celery.conf.broker_url= broker_url

#===============================
#==   CREATE APP
#===============================
logger.info("Creating and configuring app ...")
##app= create_app(config,datamgr,jobcfg)
app= create_app(config,jobcfg)
app.app_context().push()

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
if use_db and mongo is not None:
	logger.info("Initializing MongoDB to app ...")
	try:
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
