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

# Import mongo
from pymongo import MongoClient

# - caesar_rest modules
import caesar_rest
from caesar_rest import __version__, __date__
from caesar_rest import logger
from caesar_rest import jobmgr_kube
from caesar_rest import jobmgr_slurm
from caesar_rest import job_monitor
from caesar_rest.job_monitor import monitor_jobs

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
	parser.add_argument('-job_scheduler','--job_scheduler', dest='job_scheduler', default='kubernetes', required=False, type=str, help='Job scheduler to be used. Options are: {kubernetes,slurm} (default=kubernetes)')
	parser.add_argument('-job_monitoring_period','--job_monitoring_period', dest='job_monitoring_period', default=30, required=False, type=int, help='Job monitoring poll period in seconds') 
	parser.add_argument('-dbhost','--dbhost', dest='dbhost', default='localhost', required=False, type=str, help='Host of MongoDB database (default=localhost)')
	parser.add_argument('-dbname','--dbname', dest='dbname', default='caesardb', required=False, type=str, help='Name of MongoDB database (default=caesardb)')
	parser.add_argument('-dbport','--dbport', dest='dbport', default=27017, required=False, type=int, help='Port of MongoDB database (default=27017)')

	
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
	

	args = parser.parse_args()	

	return args


###########################
##     MAIN
###########################
def main():
	""" Main function """

	#===========================
	#==   PARSE ARGS
	#===========================
	logger.info("Parsing cmd line arguments ...")
	try:
		args= get_args()
	except Exception as ex:
		logger.error("Failed to get and parse options (err=%s)",str(ex))
		sys.exit(1)

	# - Main options
	job_monitoring_period= args.job_monitoring_period
	job_scheduler= args.job_scheduler
	if job_scheduler!='kubernetes' and job_scheduler!='slurm':
		logger.error("Unsupported job scheduler (hint: supported are {kubernetes,slurm})!")
		sys.exit(1)

	if job_scheduler=='kubernetes' and jobmgr_kube is None:
		logger.error("Chosen scheduler is Kubernetes but kube client failed to be instantiated (see previous logs)!")
		sys.exit(1)

	#===============================
	#==   INIT MONGO CLIENT
	#===============================
	logger.info("Initializing MongoDB client, connecting to DB (dbhost=%s, dbname=%s, dbport=%s) ..." % (args.dbhost,args.dbname,args.dbport))
	client= None
	dbport_int= int(args.dbport)
	try:
		client= MongoClient(args.dbhost, dbport_int)
	except Exception as e:
		errmsg= 'Exception caught when connecting to DB server (err=' + str(e) + ')!' 
		logger.error(errmsg)
		sys.exit(1)
		
	if client and client is not None:
		logger.info("Connected to db %s..." % args.dbname)
	else:
		logger.error("Cannot connect to DB server!")
		sys.exit(1)

	db= None
	try:
		db= client[args.dbname]
	except Exception as e:
		errmsg= 'Exception caught when connecting to DB ' + args.dbname + ' (err=' + str(e) + ')!' 
		logger.error(errmsg)
		sys.exit(1)

	if db is None:
		logger.error("DB instance is None!")
		sys.exit(1)

	#============================================
	#==   INIT KUBERNETES CLIENT (if enabled)
	#============================================
	if job_scheduler=='kubernetes' and jobmgr_kube is not None:

		# - Setting options
		jobmgr_kube.certfile= args.kube_certfile
		jobmgr_kube.cafile= args.kube_cafile
		jobmgr_kube.keyfile= args.kube_keyfile

		# - Initialize client
		logger.info("Initializing Kube job manager ...")
		try:
			if jobmgr_kube.initialize(configfile=args.kube_config, incluster=args.kube_incluster)<0:
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
		jobmgr_slurm.host= args.slurm_host
		jobmgr_slurm.port= args.slurm_port
		jobmgr_slurm.cluster_queue= args.slurm_queue
		jobmgr_slurm.keyfile= args.slurm_keyfile
		jobmgr_slurm.username= args.slurm_user
		jobmgr_slurm.cluster_batch_workdir= args.slurm_batch_workdir
		
		# - Initialize client
		logger.info("Initializing Slurm job manager ...")
		try:
			if jobmgr_slurm.initialize()<0:
				logger.error("Failed to initialize Slurm job manager, see logs!")
				sys.exit(1)
		except Exception as e:
			logger.error("Failed to initialize Slurm job manager (err=%s)!" % str(e))
			sys.exit(1)

	#============================================
	#==   MONITORING LOOP
	#============================================
	try:
		while True:
			# - Monitor jobs in DB
			logger.info("Monitoring jobs ...")
			if monitor_jobs(db)<0:
				logger.warn("Failed to monitor jobs (see logs) ...")

			# - Sleeping a bit before monitoring again
			logger.info("Sleeping %s seconds ..." % job_monitoring_period)
			time.sleep(job_monitoring_period)
						
	except KeyboardInterrupt:
		logger.info("Job monitoring interrupted with ctrl-c signal")
		return -1	


	return 0

###################
##   MAIN EXEC   ##
###################
if __name__ == "__main__":	
	#sys.exit(main())
	main()

