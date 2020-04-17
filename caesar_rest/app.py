
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

# Import config class
from caesar_rest.config import Config

## Get logger
logger = logging.getLogger(__name__)





##############################
#   APP CREATION CLASS
##############################
#logger.info("Creating Flask app using default config settings ...")

#app = Flask(__name__, instance_relative_config=True)
#app = Flask(__name__)
#app.config.from_object(Config())

def create_app(cfg,dm):
	""" Create app """

	# - Create app
	app = Flask(__name__,instance_relative_config=True)

	# - Configure app from class 
	app.config.from_object(cfg)
	
	# - Add helper classes to app
	app.config['datamgr'] = dm

	# - Register routes as blueprints
	from caesar_rest.index_route import index_bp
	from caesar_rest.upload_route import upload_bp
	from caesar_rest.download_route import download_path_bp, download_id_bp
	app.register_blueprint(index_bp)
	app.register_blueprint(upload_bp)
	app.register_blueprint(download_path_bp)
	app.register_blueprint(download_id_bp)
    
	return app


##############################
#   APP SETUP ACTIONS
##############################
#@app.before_first_request
#def register_data_files():
#	""" Register data file(s) """
#	logger.info("Running register data files ...")
	

##############################
#   APP ENDPOINTS
##############################


