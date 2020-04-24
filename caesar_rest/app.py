
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

try:
	FileNotFoundError  # python3
except NameError:
	FileNotFoundError = IOError # python2

try:
	from urllib.request import urlopen
except ImportError:
	from urllib2 import urlopen

#import urllib.request

# Import Flask
from flask import Flask
from flask import flash, request, redirect, render_template, url_for
from flask import send_file, send_from_directory, safe_join, abort
from werkzeug.utils import secure_filename

# Import Celery
#from celery import Celery
from caesar_rest import celery

# Import config class
from caesar_rest.config import Config


## Get logger
logger = logging.getLogger(__name__)


##############################
#   CELERY APP CREATION
##############################
# - Create celery class
#celery= Celery(
#	__name__
#)

# - When called configure celery 
def configure_celery_app(app):
	""" Create a Celery app """
    
	# - Configure app from Flask config
	#celery.conf.update(app.config)

	# - Subclass task
	TaskBase = celery.Task
	class ContextTask(TaskBase):
		abstract = True
		def __call__(self, *args, **kwargs):
			with app.app_context():
				return TaskBase.__call__(self, *args, **kwargs)
    
	celery.Task = ContextTask

	
##############################
#   FLASK APP CREATION 
##############################
def create_app(cfg,dm,jc):
	""" Create app """

	# - Create app
	app = Flask(__name__,instance_relative_config=True)

	# - Configure app from class 
	app.config.from_object(cfg)
	
	# - Add helper classes to app
	app.config['datamgr'] = dm
	app.config['jobcfg'] = jc

	# - Configure Celery app
	configure_celery_app(app)

	# - Register routes as blueprints
	from caesar_rest.index_route import index_bp
	from caesar_rest.upload_route import upload_bp
	from caesar_rest.download_route import download_path_bp, download_id_bp
	from caesar_rest.job_route import job_bp, job_status_bp, job_output_bp, job_cancel_bp
	app.register_blueprint(index_bp)
	app.register_blueprint(upload_bp)
	app.register_blueprint(download_path_bp)
	app.register_blueprint(download_id_bp)
	app.register_blueprint(job_bp)
	app.register_blueprint(job_status_bp)
	app.register_blueprint(job_output_bp)
	app.register_blueprint(job_cancel_bp)
    
	return app




