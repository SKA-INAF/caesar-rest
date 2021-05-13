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
	SLURM_CAESAR_JOB_IMAGE= '/opt/containers/caesar/caesar-job_latest.sif'
	
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


