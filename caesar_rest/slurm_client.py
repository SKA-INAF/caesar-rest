##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import glob
import signal
import sys
import json
import time
import datetime
from datetime import datetime, timedelta, timezone
from dateutil.tz import tzutc
import logging
import numpy as np
import pprint

# - Import additional modules
import requests
#import pyjwt
from jwt import JWT
from jwt.jwa import HS256
from jwt.jwk import jwk_from_dict
from jwt.utils import b64decode,b64encode

# - Import CAESAR-REST modules
from caesar_rest import utils

# - Get logger
logger = logging.getLogger(__name__)

##############################
#      CLASSES
##############################
class SlurmJobManager(object):
	""" A wrapper class to manage Slurm jobs """    
	
	def __init__(self):
	
		self.host= ''
		self.port= 6820
		self.cluster_url= ''
		self.cluster_queue= ''
		self.token= '' # JWT token
		self.keyfile= '' # Path of Slurm REST key file, e.g. /etc/slurm/jwt.key
		self.key= ''
		self.username= ''
		

	#############################
	##  SET CLUSTER URL
	#############################
	def set_cluster_url(self):
		""" Set cluster url """
		
		self.cluster_url= 'http://' + self.host + ':' + str(self.port) + '/slurm/v0.0.36' 

	#############################
	##   INITIALIZE
	#############################
	def initialize(self):
		""" Initialize client """

		# - Check if required field were set
		# ...		
		# ...

		# - Set cluster url
		self.set_cluster_url()

		# - Read private key
		if self.read_key<0:
			logger.warn("Failed to read Slurm rest private key!")
			return -1

		# - Generate a token
		if self.generate_token()<0:
			logger.warn("Failed to generate Slurm JWT token!")
			return -1

		# ...
		# ...

		return 0

	#############################
	##   READ KEY
	#############################
	def read_key(self):
		""" Read private key """
		
		# - Read private key
		try:
			with open(self.keyfile, "rb") as f:
				priv_key= f.read()
				self.key = jwk_from_dict({'kty': 'oct', 'k': b64encode(priv_key)})

		except Exception as e:
			logger.warn("Failed to read private key from file %s (err=%s)!" % (self.keyfile,str(e)))
			return -1

		return -1

	#############################
	##   GENERATE AUTH TOKEN
	#############################
	def generate_token(self, duration=3600):
		""" Generate a token for user from key with duration in seconds """

		# - Taken from https://slurm.schedmd.com/jwt.html#:~:text=Version%2020.11-,JSON%20Web%20Tokens%20(JWT)%20Authentication,connecting%20to%20slurmctld%20and%20slurmdbd.
		now= time.time()
		expiration_time= int(now + int(duration))
		message = {
			"exp": expiration_time,
			"iat": int(now),
			"sun": self.username
		}

		# - Generate token
		jwt_token= ''
		try:
			jwt_instance = JWT()
			jwt_token= jwt_instance.encode(message, signing_key, alg='HS256')
		except Exception as e:
			logger.warn("Failed to generate token (err=%s)" % str(e))
			return -1

		if jwt_token=="" or jwt_token is None:
			logger.warn("Generate token is empty string or None, something went wrong, do not update token!")
			return -1
		else:
			self.token= jwt_token

		return 0


	#############################
	##   SUBMIT JOB
	#############################
	def submit_job(self, job_data):
		""" Submit a job to Slurm cluster """

		#####################################
		##  API RESPONSE 
		##  {
  	##     "job_id" : 0,
  	##     "step_id" : "step_id",
  	##     "errors" : [{"errno": 0,"error": "error"}, {"errno" : 0, "error" : "error"}],
  	##     "job_submit_user_msg" : "job_submit_user_msg"
		##  }
		#####################################

		# - Set header
		headers = {
			'Content-Type': 'application/json',
			'X-SLURM-USER-NAME': self.username,
			'X-SLURM-USER-TOKEN': self.token,
		}

		# - Set url
		url= self.cluster_url + '/job/submit'

		# - Submit job
		logger.info("Submitting job (data=%s, url=%s) ..." % (job_data, url))
		jobout= None
		try:
			jobout= requests.post(
				url, 
				headers=headers, 
				data=job_data
			)
			print("--> slurm jobout")
			print(jobout)

		except Exception as e:
			logger.warn("Failed to submit job to url %s (err=%s)" % (url,str(e)))
			return None

		# - Parse reply and convert to dictionary
		reply= None
		try:
			reply= json.loads(jobout.text)
		except Exception as e:
			logger.warn("Failed to convert reply to dict (err=%s)!" % str(e))
			return None

		return reply


	#===============================================
	#==     CREATE JOB WITH PRE-MOUNTED VOLUME
	#===============================================
	def create_job(self, image, job_args, inputfile, job_name="", job_outdir=""):
		""" Create a standard job object with rclone mounted volume """

		# - Check job options
		if job_args=="":
			logger.warn("Empty job args given!")
			return None

		if inputfile=="":
			logger.warn("Empty inputfile given!")
			return None			

		if job_name=="":
			job_name= utils.get_uuid()

		#############################
		###   CREATE JOB SCRIPT
		#############################
		# - Set env vars
		job_dir= ''.join("/home/%s/%s" % (self.username, job_name))

		env_vars= ""
		env_vars+= "".join("--env CHANGE_RUNUSER=0 ")
		env_vars+= "".join("--env JOB_DIR=%s " % job_dir)
		env_vars+= "".join("--env JOB_OPTIONS=%s " % job_args)		
		env_vars+= "".join("--env JOB_OUTDIR=%s " % job_outdir)

		# - Set singularity run options
		run_opts= "--containall "

		# - Set singularity volume mount options
		vol_opts= ""
		vol_opts+= "".join("--scratch %s " % job_dir)
		vol_opts+= "".join("-B %s " % job_outdir)
		vol_opts+= "".join("-B %s " % inputfile)
		
		# - Set run command
		cmd= "singularity run "
		cmd+= run_opts
		cmd+= vol_opts
		cmd+= env_vars
		cmd+= image
		
		# - Set job script
		script= "#!/bin/bash \n"
		script+= "".join("%s \n" % cmd)
		
		logger.info("Slurm script: %s" % script)

		#############################
		###   CREATE JOB BODY
		#############################
		#  NB: See other options @ https://slurm.schedmd.com/rest_api.html#v0.0.36_job_properties

		# - Set job out log file
		job_logfile= job_outdir + "/job_" + job_name + ".log"
		
		# - Create job object
		#   NB: This is the minimal options needed. The environment field seems mandatory contrarily to what specified in the doc.
		job_data_obj= {}
		job_data_obj["script"]= script
		job_data_obj["job"]= {
			"name": job_name,
			"environment": {"PATH":"/bin:/usr/bin/:/usr/local/bin/"},
			"partition": self.cluster_queue,
		#	"current_working_directory": job_outdir,
		# "standard_out": job_logfile,
		# "standard_error": job_logfile,
		}

		# - Convert dict to string
		job_data= ""
		try:
			job_data= json.dumps(job_data_obj)
		except Exception as e:
			logger.warn("Failed to convert job data to string (err=%s)" % str(e))
			return None	 

		logger.info("Slurm job data: %s" % job_data)

		return job_data


