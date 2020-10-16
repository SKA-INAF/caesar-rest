##############################
#   MODULE IMPORTS
##############################
# Import standard modules
import os
import signal
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

# Import flask modules
from flask import current_app, Blueprint, render_template, request, redirect, url_for
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
from werkzeug.utils import secure_filename
from caesar_rest import oidc
from caesar_rest.decorators import custom_require_login


# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINTS
##############################
app_names_bp = Blueprint('app_names', __name__,url_prefix='/caesar/api/v1.0')
app_describe_bp = Blueprint('app_describe', __name__,url_prefix='/caesar/api/v1.0')


@app_names_bp.route('/apps',methods=['GET'])
@custom_require_login
def get_app_names():
	""" Get supported apps """

	app_names= current_app.config['jobcfg'].get_app_names()
	return make_response(jsonify(app_names),200)


@app_describe_bp.route('/app/<app_name>/describe',methods=['GET'])
@custom_require_login
def get_app_description(app_name):
	""" Get description of given app """

	res= {}
	res['status']= ''
	app_description= current_app.config['jobcfg'].get_app_description(app_name)
	if app_description is None:
		res['status']= 'Unknown app ' + app_name + '!'
		return make_response(jsonify(res),400)

	return make_response(jsonify(app_description),200)

