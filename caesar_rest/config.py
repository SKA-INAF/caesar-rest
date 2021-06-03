#! /usr/bin/env python

##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import sys
import uuid

# Import module files
##from caesar_rest.data_manager import DataManager ## DEPRECATED
from caesar_rest.job_configurator import JobConfigurator

import structlog

##############################
#   APP CONFIG CLASS
##############################

class Config(object):
	""" Class holding configuration options for Flask app """

	# - Flask Options
	DEBUG = False
	TESTING = False
	SECRET_KEY= uuid.uuid4().hex
	UPLOAD_FOLDER= '/opt/caesar-rest/data'
	MAX_CONTENT_LENGTH= 1000 * 1024 * 1024 # 16 MB

	# - Additional options
	JOB_DIR= '/opt/caesar-rest/jobs'
	UPLOAD_ALLOWED_FILE_FORMATS= set(['png', 'jpg', 'jpeg', 'gif', 'fits'])
	JOB_MONITORING_PERIOD= 5 # in seconds

	JOB_SCHEDULER= 'celery' # Options are: {'celery','kubernetes','slurm'}

	# - VOLUME MOUNTS options
	MOUNT_RCLONE_VOLUME= False
	MOUNT_VOLUME_PATH= '/mnt/storage'
	RCLONE_REMOTE_STORAGE= 'neanias-nextcloud'
	RCLONE_REMOTE_STORAGE_PATH= '.'
	RCLONE_SECRET_NAME= 'rclone-secret'

	# - KUBERNETES options
	KUBE_CONFIG_PATH= '' # searches by default in $HOME/.kube/config or in $KUBECONFIG
	KUBE_INCLUSTER= True # if True assume client is running inside a pod deployed in same cluster, if False client is external to cluster
	KUBE_CERTFILE= ''
	KUBE_KEYFILE= ''
	KUBE_CERTAUTHFILE= ''

	# - SLURM options
	SLURM_KEYFILE= ''
	SLURM_QUEUE= 'normal'
	SLURM_USER= 'cirasa'
	SLURM_HOST= 'lofar-gpu-01.oact.inaf.it'	# 'cirasa host'
	SLURM_PORT= 6820
	SLURM_BATCH_WORKDIR= '/opt/caesar-rest/batchlogs'
	SLURM_JOB_DIR= '/mnt/storage/jobs'  # Path at which the job directory is mounted in Slurm cluster 
	SLURM_DATA_DIR= '/mnt/storage/data' # Path at which the data directory is mounted in Slurm cluster
	SLURM_CAESAR_JOB_IMAGE= '/opt/containers/caesar/caesar-job_latest.sif'
	SLURM_MASKRCNN_JOB_IMAGE= '/opt/containers/mrcnn/mrcnn-detect_latest.sif'
	SLURM_MAX_CORE_PER_JOB= 4 # Maximum number of cores reserved for a job
	
	# - AAI options
	USE_AAI = False
	OIDC_CLIENT_SECRETS = 'config/client_secrets.json'
	OIDC_OPENID_REALM = 'neanias-development'
	OIDC_SCOPES = ['openid', 'email', 'profile']

	# - MONG DB options
	USE_MONGO = False
	MONGO_HOST= 'localhost'
	MONGO_PORT= 27017
	MONGO_DBNAME= 'caesardb' 
	MONGO_URI= 'mongodb://localhost:27017/caesardb'

	# - CAESAR app options
	CAESAR_JOB_IMAGE= 'sriggi/caesar-job:latest'
	
	# - Mask R-CNN app options
	MASKRCNN_JOB_IMAGE= 'sriggi/mrcnn-detect:latest'
	MASKRCNN_WEIGHTS= '/opt/Software/MaskR-CNN/install/share/mrcnn_weights.h5'


	# - Logging configuration
	LOG_TO_FILE= False
	LOG_DIR= '/opt/caesar-rest/logs'
	LOG_FILE= 'app_logs.json'
	LOG_LEVEL= 'INFO'

#	LOGGING = {
#		"version": 1,
#		"disable_existing_loggers": False,
#		"formatters": {
#			"json_formatter": {
#				"()": structlog.stdlib.ProcessorFormatter,
#				"processor": structlog.processors.JSONRenderer(),
#			},
#			"plain_console": {
#				"()": structlog.stdlib.ProcessorFormatter,
#				"processor": structlog.dev.ConsoleRenderer(),
#			},
#			"key_value": {
#				"()": structlog.stdlib.ProcessorFormatter,
#				"processor": structlog.processors.KeyValueRenderer(key_order=['timestamp', 'level', 'event', 'logger']),
#			},
#		},
#		"handlers": {
#			"console": {
#				"class": "logging.StreamHandler",
#				"formatter": "plain_console",
#			},
#			"json_file": {
#				"class": "logging.handlers.RotatingFileHandler",
#				"filename": os.path.join(LOG_DIR, LOG_FILE),
#				"formatter": "json_formatter",
#				"maxBytes": 5*1024*1024, # 5 MB
#				"backupCount": 2
#			},
#		},
#		"loggers": {
#			'app_caesar': {
#				'handlers': ['console', 'json_file'],
#				'level': LOG_LEVEL,
#			}
#		}
#	}


#	structlog.configure(
#		processors=[
#			structlog.stdlib.filter_by_level,
#			structlog.processors.TimeStamper(fmt="iso"),
#			structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
#			structlog.stdlib.add_logger_name,
#			structlog.stdlib.add_log_level,
#			structlog.stdlib.PositionalArgumentsFormatter(),
#			structlog.processors.StackInfoRenderer(),
#			structlog.processors.format_exc_info,
#			structlog.processors.UnicodeDecoder(),
#			structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
#		],
#		context_class=structlog.threadlocal.wrap_dict(dict),
#		logger_factory=structlog.stdlib.LoggerFactory(),
#		wrapper_class=structlog.stdlib.BoundLogger,
#		cache_logger_on_first_use=True,
#	)




