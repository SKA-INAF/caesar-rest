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

import structlog
import logging

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
from caesar_rest import jobmgr_kube
from caesar_rest import jobmgr_slurm

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
	parser.add_argument('-job_scheduler','--job_scheduler', dest='job_scheduler', default='celery', required=False, type=str, help='Job scheduler to be used. Options are: {celery,kubernetes,slurm} (default=celery)')
	parser.add_argument('-job_monitoring_period','--job_monitoring_period', dest='job_monitoring_period', default=5, required=False, type=int, help='Job monitoring poll period in seconds') 
	parser.add_argument('--debug', dest='debug', action='store_true')	
	parser.set_defaults(debug=True)

	# - Log options
	parser.add_argument('-loglevel','--loglevel', dest='loglevel', default='INFO', required=False, type=str, help='Log level to be used (default=INFO)')
	parser.add_argument('--logtofile', dest='logtofile', action='store_true')	
	parser.set_defaults(logtofile=False)
	parser.add_argument('-logdir','--logdir', dest='logdir', default='/opt/caesar-rest/logs', required=False, type=str, help='Directory where to store logs')
	parser.add_argument('-logfile','--logfile', dest='logfile', default='app_logs.json', required=False, type=str, help='Name of json log file')
	parser.add_argument('-logfile_maxsize','--logfile_maxsize', dest='logfile_maxsize', default=5.0, required=False, type=float, help='Max file size in MB (default=5)')


	# - AAI options
	parser.add_argument('--aai', dest='aai', action='store_true')	
	parser.set_defaults(aai=False)	
	parser.add_argument('-secretfile','--secretfile', dest='secretfile', default='config/client_secrets.json', required=False, type=str, help='File (.json) with client credentials for AAI')
	parser.add_argument('-openid_realm','--openid_realm', dest='openid_realm', default='neanias-development', required=False, type=str, help='OpenID realm used in AAI (defaul=neanias-development)') 
	parser.add_argument('--ssl', dest='ssl', action='store_true')	
	parser.set_defaults(ssl=False)
	
	# - Algorithm options
	parser.add_argument('-mrcnn_weights','--mrcnn_weights', dest='mrcnn_weights', default='/opt/Software/MaskR-CNN/install/share/mrcnn_weights.h5', required=False, type=str, help='File (.h5) with network weights used in Mask-RCNN app')

	# - DB options
	parser.add_argument('--no-db', dest='db', action='store_false')
	parser.add_argument('--db', dest='db', action='store_true')	
	parser.set_defaults(db=True)
	parser.add_argument('-dbhost','--dbhost', dest='dbhost', default='localhost', required=False, type=str, help='Host of MongoDB database (default=localhost)')
	parser.add_argument('-dbname','--dbname', dest='dbname', default='caesardb', required=False, type=str, help='Name of MongoDB database (default=caesardb)')
	parser.add_argument('-dbport','--dbport', dest='dbport', default=27017, required=False, type=int, help='Port of MongoDB database (default=27017)')

	# - Celery options
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

	# - Kubernetes scheduler options
	parser.add_argument('--kube_incluster', dest='kube_incluster', action='store_true')	
	parser.set_defaults(kube_incluster=False)
	parser.add_argument('-kube_config','--kube_config', dest='kube_config', default='', required=False, type=str, help='Kube configuration file path (default=search in standard path)')
	parser.add_argument('-kube_cafile','--kube_cafile', dest='kube_cafile', default='', required=False, type=str, help='Kube certificate authority file path')
	parser.add_argument('-kube_keyfile','--kube_keyfile', dest='kube_keyfile', default='', required=False, type=str, help='Kube private key file path')
	parser.add_argument('-kube_certfile','--kube_certfile', dest='kube_certfile', default='', required=False, type=str, help='Kube certificate file path')
	
	# - Slurm scheduler options
	parser.add_argument('-slurm_keyfile','--slurm_keyfile', dest='slurm_keyfile', default='', required=False, type=str, help='Slurm rest service private key file path')
	parser.add_argument('-slurm_user','--slurm_user', dest='slurm_user', default='cirasa', required=False, type=str, help='Username enabled to run in Slurm cluster')
	parser.add_argument('-slurm_host','--slurm_host', dest='slurm_host', default='SLURM_HOST', required=False, type=str, help='Slurm cluster host/ipaddress')
	parser.add_argument('-slurm_port','--slurm_port', dest='slurm_port', default=6820, required=False, type=int, help='Slurm rest service port')
	parser.add_argument('-slurm_batch_workdir','--slurm_batch_workdir', dest='slurm_batch_workdir', default='', required=False, type=str, help='Cluster directory where to place Slurm batch logs (must be writable by slurm_user)')
	parser.add_argument('-slurm_queue','--slurm_queue', dest='slurm_queue', default='normal', required=False, type=str, help='Slurm cluster host/ipaddress')
	parser.add_argument('-slurm_jobdir','--slurm_jobdir', dest='slurm_jobdir', default='/mnt/storage/jobs', required=False, type=str, help='Path at which the job directory is mounted in Slurm cluster')	
	parser.add_argument('-slurm_datadir','--slurm_datadir', dest='slurm_datadir', default='/mnt/storage/data', required=False, type=str, help='Path at which the data directory is mounted in Slurm cluster')	

	# - Volume mount options
	parser.add_argument('--mount_rclone_volume', dest='mount_rclone_volume', action='store_true')	
	parser.set_defaults(mount_rclone_volume=False)
	parser.add_argument('-mount_volume_path','--mount_volume_path', dest='mount_volume_path', default='/mnt/storage', required=False, type=str, help='Mount volume path for container jobs')
	parser.add_argument('-rclone_storage_name','--rclone_storage_name', dest='rclone_storage_name', default='neanias-nextcloud', required=False, type=str, help='rclone remote storage name (default=neanias-nextcloud)')
	parser.add_argument('-rclone_storage_path','--rclone_storage_path', dest='rclone_storage_path', default='.', required=False, type=str, help='rclone remote storage path (default=.)')
	
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

# - Log level options
loglevel= args.loglevel
logtofile= args.logtofile
logdir= args.logdir
logfile= args.logfile
logfilepath= os.path.join(logdir,logfile)
logfile_maxsize= args.logfile_maxsize

if logtofile:
	logger.info("Enabling logging to file %s ..." % logfilepath)
	
	formatter_file= structlog.stdlib.ProcessorFormatter(
		processor=structlog.processors.JSONRenderer(),
	)

	try:
		handler_file= logging.handlers.RotatingFileHandler(
			logfilepath, 
			maxBytes=logfile_maxsize*1024*1024,
			backupCount=2 
		)
	except Exception as e:
		logger.error("Failed to initialize file logger (err=%s)!" % str(e))
		sys.exit(1)

	handler_file.setFormatter(formatter_file)
	logger.addHandler(handler_file)

logger.info("Setting log level to %s ..." % loglevel)
logger.setLevel(loglevel)



# - AAI options
use_aai= args.aai
secret_file= args.secretfile
openid_realm= args.openid_realm
ssl= args.ssl

# - App options
job_monitoring_period= args.job_monitoring_period
mrcnn_weights= args.mrcnn_weights

# - Scheduler options
job_scheduler= args.job_scheduler
if job_scheduler!='celery' and job_scheduler!='kubernetes' and job_scheduler!='slurm':
	logger.error("Unsupported job scheduler (hint: supported are {celery,kubernetes,slurm})!")
	sys.exit(1)

if job_scheduler=='kubernetes' and jobmgr_kube is None:
	logger.error("Chosen scheduler is Kubernetes but kube client failed to be instantiated (see previous logs)!")
	sys.exit(1)

# - DB & celery result backend options
use_db= args.db
dbhost= 'mongodb://' + args.dbhost + ':' + str(args.dbport) + '/' + args.dbname

if use_db:
	logger.info("Using db url: %s" % dbhost)
else:
	logger.warn("DB usage is disabled...")

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

if job_scheduler=='celery':
	logger.info("Using result_backend: %s" % result_backend)


# - Celery broker options
broker_host= args.broker_host
broker_port= args.broker_port
broker_proto= args.broker_proto
broker_user= args.broker_user
broker_pass= args.broker_pass 
broker_url= broker_proto + '://' + broker_user + ':' + broker_pass + '@' + broker_host + ':' + str(broker_port) + '/'

if job_scheduler=='celery':
	logger.info("Using broker_url: %s" % broker_url)


# - Kubernetes options
kube_incluster= args.kube_incluster
kube_config= args.kube_config
kube_certfile= args.kube_certfile
kube_keyfile= args.kube_keyfile
kube_cafile= args.kube_cafile

# - Slurm options
slurm_keyfile= args.slurm_keyfile
slurm_user= args.slurm_user
slurm_host= args.slurm_host
slurm_port= args.slurm_port
slurm_batch_workdir= args.slurm_batch_workdir
slurm_queue= args.slurm_queue
slurm_jobdir= args.slurm_jobdir
slurm_datadir= args.slurm_datadir
	
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

config.MASKRCNN_WEIGHTS = mrcnn_weights

config.JOB_SCHEDULER= job_scheduler
config.KUBE_CONFIG_PATH= kube_config
config.KUBE_INCLUSTER= kube_incluster
config.KUBE_CERTFILE= kube_certfile
config.KUBE_KEYFILE= kube_keyfile
config.KUBE_CERTAUTHFILE= kube_cafile

config.SLURM_KEYFILE= slurm_keyfile
config.SLURM_QUEUE= slurm_queue
config.SLURM_USER= slurm_user
config.SLURM_HOST= slurm_host
config.SLURM_BATCH_WORKDIR= slurm_batch_workdir
config.SLURM_PORT= slurm_port
config.SLURM_JOB_DIR= slurm_jobdir
config.SLURM_DATA_DIR= slurm_datadir


config.MOUNT_RCLONE_VOLUME= args.mount_rclone_volume
config.MOUNT_VOLUME_PATH= args.mount_volume_path
config.RCLONE_REMOTE_STORAGE= args.rclone_storage_name
config.RCLONE_REMOTE_STORAGE_PATH= args.rclone_storage_path

config.LOG_TO_FILE= logtofile
config.LOG_LEVEL= loglevel
config.LOG_DIR= logdir
config.LOG_FILE= logfile

# - Create data manager (DEPRECATED BY MONGO)
##logger.info("Creating data manager ...")
##datamgr= DataManager(rootdir=config.UPLOAD_FOLDER)
##datamgr.register_data()

# - Create job configurator
logger.info("Creating job configurator ...")
jobcfg= JobConfigurator()

# - Update celery configs
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

#============================================
#==   INIT KUBERNETES CLIENT (if enabled)
#============================================
if job_scheduler=='kubernetes' and jobmgr_kube is not None:

	# - Setting options
	jobmgr_kube.certfile= config.KUBE_CERTFILE
	jobmgr_kube.cafile= config.KUBE_CERTAUTHFILE
	jobmgr_kube.keyfile= config.KUBE_KEYFILE

	# - Initialize client
	logger.info("Initializing Kube job manager ...")
	try:
		if jobmgr_kube.initialize(configfile=config.KUBE_CONFIG_PATH, incluster=config.KUBE_INCLUSTER)<0:
			logger.error("Failed to initialize Kube job manager, see logs!")
			sys.exit(1)
	except Exception as e:
		logger.error("Failed to initialize Kube job manager (err=%s)!" % str(e))
		sys.exit(1)

#============================================
#==   INIT SLURM CLIENT (if enabled)
#============================================
if job_scheduler=='slurm' and jobmgr_slurm is not None:

	# - Setting options
	jobmgr_slurm.host= config.SLURM_HOST
	jobmgr_slurm.port= config.SLURM_PORT	
	jobmgr_slurm.cluster_queue= config.SLURM_QUEUE
	jobmgr_slurm.keyfile= config.SLURM_KEYFILE
	jobmgr_slurm.username= config.SLURM_USER
	jobmgr_slurm.cluster_batch_workdir= config.SLURM_BATCH_WORKDIR
	jobmgr_slurm.cluster_jobdir= config.SLURM_JOB_DIR
	jobmgr_slurm.cluster_datadir= config.SLURM_DATA_DIR
	jobmgr_slurm.app_jobdir= config.JOB_DIR
	jobmgr_slurm.app_datadir= config.UPLOAD_FOLDER

	# - Initialize client
	logger.info("Initializing Slurm job manager ...")
	try:
		if jobmgr_slurm.initialize()<0:
			logger.error("Failed to initialize Slurm job manager, see logs!")
			sys.exit(1)
	except Exception as e:
		logger.error("Failed to initialize Slurm job manager (err=%s)!" % str(e))
		sys.exit(1)


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
