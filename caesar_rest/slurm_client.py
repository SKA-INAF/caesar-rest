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
import jwt
from jwt import JWT
from jwt.jwa import HS256
from jwt.jwk import jwk_from_dict
from jwt.utils import b64decode,b64encode,get_time_from_int

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
	
		# - Options to be set
		self.host= ''
		self.port= 6820
		self.username= ''
		self.cluster_batch_workdir= ''
		self.cluster_queue= ''
		self.keyfile= '' # Path of Slurm REST key file, e.g. /etc/slurm/jwt.key
			
		# - Options read or automatically computed from others
		self.cluster_url= ''
		self.key= ''
		self.token= '' # JWT token


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
		if self.username=="":
			logger.warn("Empty cluster username given, check given app options!")
			return -1

		if self.host=="":
			logger.warn("Empty cluster hostname given, check given app options!")
			return -1

		if self.cluster_queue=="":
			logger.warn("Empty cluster queue given, check given app options!")
			return -1

		if self.keyfile=="":
			logger.warn("Empty Slurm key file given, check given app options!")
			return -1

		if not os.path.isfile(self.keyfile):
			logger.warn("Slurm key file %s not existing on filesystem!" % self.keyfile)
			return -1

		if self.cluster_batch_workdir=="":
			logger.warn("Slurm cluster batch workdir not given...setting it to /home/%s ..." % self.username)
			self.cluster_batch_workdir= '/home/' + self.username

		# - Set cluster url
		self.set_cluster_url()

		# - Read private key
		if self.read_key()<0:
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

		return 0

	

	####################################
	##   GENERATE/VALIDAT AUTH TOKEN
	####################################
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
			jwt_token= jwt_instance.encode(message, self.key, alg='HS256')
		except Exception as e:
			logger.warn("Failed to generate token (err=%s)" % str(e))
			return -1

		if jwt_token=="" or jwt_token is None:
			logger.warn("Generate token is empty string or None, something went wrong, do not update token!")
			return -1
		else:
			self.token= jwt_token

		# - Check token
		if not self.is_token_valid():
			logger.warn("Generated token is invalid, set to empty string.")
			self.token= ""
			return -1

		return 0

	def is_token_active(self):
		""" Check if token is valid and not expired """

		payload= self.decode_token(verify=True, check_exp=True)
		if payload is None:
			return False

		return True
	
	def is_token_valid(self):
		""" Check if token is valid """

		payload= self.decode_token(verify=True)
		if payload is None:
			return False

		return True
		
	def is_token_expired(self):
		""" Check if token is valid and expired """

		payload= self.decode_token(verify=False, check_exp=True)
		if payload is None:
			return True

		return False
		

	def decode_token(self, verify=True, check_exp=False):
		""" Check if token is valid """

		signing_key= None
		if verify:
			signing_key= self.key

		try:
			jwt_instance = JWT()
			payload = jwt_instance.decode(
				self.token, 
				key=signing_key, 
				algorithms=["HS256"],
				do_verify=verify,
				do_time_check=check_exp
			)
			#print(payload)
	
		except jwt.exceptions.JWTDecodeError as e:
			logger.warn("Failed to decode token (err=%s)" % str(e))
			return None

		except Exception as e:
			logger.warn("Exception caught when decoding token (err=%s)" % str(e))
			return None

		return payload

	def get_token_time_left(self):
		""" Returns the number of seconds left before token expiration """

		# - Get token payload
		payload= self.decode_token(verify=True, check_exp=True)
		if payload is None:
			logger.warn("Current token is not valid or expired, cannot get expiration time data!")
			return -999

		# - Get expiration time date
		if 'exp' not in payload:
			logger.warn("Cannot find exp field in token payload!")
			return -999

		try:
			expiration_date= get_time_from_int(payload['exp'])
		except TypeError:
			logger.warn("Invalid expired time field read (expected int)!")
			return -999

		# - Compute time diff wrt now
		now = datetime.now(timezone.utc)
		tdiff= expiration_date-now
		tdiff_sec= tdiff.total_seconds()

		print("tdiff")
		print(tdiff)

		return tdiff_sec
		

	def renew_token(self, time_to_expire_thr=30, duration=3600):
		""" Regenerate token if expiration time is less then given threshold """

		# - Check time left
		tdiff= self.get_token_time_left()
		status= 0
		if tdiff<=0:
			logger.info("Current token is invalid or expired, regenerating ...")
			status= self.generate_token(duration)

		elif tdiff>0 and tdiff<time_to_expire_thr:
			logger.info("Current token is about to expire (tdiff=%f), regenerating ..." % tdiff)
			status= self.generate_token(duration)
		
		else:
			logger.debug("Current token is still valid (expiring in %f seconds) ..." % tdiff)
			status= 0

		return status

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

		# - Check token is active
		if not self.is_token_active():
			logger.warn("Slurm rest auth token not valid or expired, regenerating it ...")
			if self.generate_token()<0:
				logger.warn("Failed to regenerate Slurm auth token, cannot submit job!")
				return None
		 

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
		env_vars+= "".join("--env JOB_OPTIONS=\'%s\' " % job_args)		
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
		script= "#!/bin/bash \n "
		script+= "".join("%s" % cmd)
		
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
      "current_working_directory": self.cluster_batch_workdir, # this is somewhat needed otherwise slurm tries to write to / and get a permission output error
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


	#============================
	#==     GET JOB STATUS
	#============================
	def get_job_status(self, job_pid):
		""" Retrieve job status """

		# - Init response
		res= {}
		#res['job_id']= job_name
		res['pid']= job_pid
		res['state']= ''
		res['status']= ''
		res['exit_code']= ''
		res['elapsed_time']= ''

		# - Check token is active
		if not self.is_token_active():
			logger.warn("Slurm rest auth token not valid or expired, regenerating it ...")
			if self.generate_token()<0:
				logger.warn("Failed to regenerate Slurm auth token, cannot submit job!")
				return None
		 
		# - Set header
		headers = {
			'Content-Type': 'application/json',
			'X-SLURM-USER-NAME': self.username,
			'X-SLURM-USER-TOKEN': self.token,
		}

		# - Set url
		url= self.cluster_url + '/job/' + job_pid


		# - Get job status
		logger.info("Retrieving job status (pid=%s, url=%s) ..." % (job_pid, url))
		jobout= None
		try:
			jobout= requests.get(
				url, 
				headers=headers, 
			)
			print("--> slurm jobout")
			print(jobout)

		except Exception as e:
			logger.warn("Failed to query job status to url %s (err=%s)" % (url,str(e)))
			return None

		# - Parse reply and convert to dictionary
		reply= None
		try:
			reply= json.loads(jobout.text)
		except Exception as e:
			logger.warn("Failed to convert reply to dict (err=%s)!" % str(e))
			return None

		job_objs= reply["jobs"]
		if not job_objs:
			logger.warn("Empty job status reply, job not found or already cleared in Slurm")
			return None
		
		job_obj= job_objs[0]

		# - Map state
		#   NB: Slurm returns these states: {"PENDING","COMPLETED","RUNNING","SUSPENDED","CANCELLED","FAILED","TIMEOUT","NODE_FAIL","PREEMPTED","BOOT_FAIL","DEADLINE","OUT_OF_MEMORY"}
		job_state= job_obj["job_state"]
		if job_state=="PENDING":
			res['state']= 'PENDING'
			res['status']= 'Job queued and waiting for initiation'

		elif job_state=="RUNNING":
			res['state']= 'RUNNING'
			res['status']= 'Job executing'

		elif job_state=="COMPLETED":
			res['state']= 'SUCCESS'
			res['status']= 'Job completed execution successfully'

		elif job_state=="SUSPENDED":
			res['state']= 'PENDING'
			res['status']= 'Job was suspended'

		elif job_state=="CANCELLED":
			res['state']= 'CANCELED'
			res['status']= 'Job was canceled by user'

		elif job_state=="FAILED":
			res['state']= 'FAILURE'
			res['status']= 'Job completed execution unsuccessfully'
	
		elif job_state=="TIMEOUT":
			res['state']= 'TIMED-OUT'
			res['status']= 'Job terminated due to time limit reached'
		
		elif job_state=="NODE_FAIL":
			res['state']= 'FAILURE'
			res['status']= 'Job terminated due to node failure'

		elif job_state=="PREEMPTED":
			res['state']= 'FAILURE'
			res['status']= 'Job terminated due to preemption'

		elif job_state=="BOOT_FAIL":
			res['state']= 'FAILURE'
			res['status']= 'Job terminated due to node boot failure'

		elif job_state=="DEADLINE":
			res['state']= 'FAILURE'
			res['status']= 'Job terminated on deadline'

		elif job_state=="OUT_OF_MEMORY":
			res['state']= 'FAILURE'
			res['status']= 'Job terminated due to experienced out of memory error'

		else:
			res['state']= 'UNKNOWN'
			res['status']= 'Job currently in unknown state (raw state=' + job_state + ')'
  
		# - Get elapsed time
		t0= job_obj["start_time"]
		t1= job_obj["end_time"]
		elapsed= (t1-t0)
		res['elapsed_time']= elapsed

		# - Get exit code
		res['exit_code']= job_obj["exit_code"]

		return res


	#============================
	#==     DELETE JOB
	#============================
	def delete_job(self, job_pid):
		""" Cancel a job """
		
		# - Check token is active
		if not self.is_token_active():
			logger.warn("Slurm rest auth token not valid or expired, regenerating it ...")
			if self.generate_token()<0:
				logger.warn("Failed to regenerate Slurm auth token, cannot submit job!")
				return None
		 
		# - Set header
		headers = {
			'Content-Type': 'application/json',
			'X-SLURM-USER-NAME': self.username,
			'X-SLURM-USER-TOKEN': self.token,
		}

		# - Set url
		url= self.cluster_url + '/job/' + job_pid

		logger.info("Deleting job with pid=%s ..." % job_pid)
		status_code= 0
		try:
			reply= requests.delete(
				url, 
				headers=headers, 
			)
			print("--> slurm reply to delete")
			print(reply)

			status_code= reply.status_code	

		except Exception as e:
			logger.warn("Failed to delete job with url %s (err=%s)" % (url,str(e)))
			return None

		# - Check status code
		if status_code==200:
			logger.info("Job with pid=%s deleted with success" % job_pid)
		else:
			logger.warn("Failed to delete job with pid %s (err=server replied with status code %d)!" % (job_pid,status_code))
			return -1

		return 0


