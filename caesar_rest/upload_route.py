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
import uuid

try:
	FileNotFoundError  # python3
except NameError:
	FileNotFoundError = IOError # python2

try:
	from urllib.request import urlopen
except ImportError:
	from urllib2 import urlopen

# import Flask modules
from flask import current_app, Blueprint, flash, request, redirect, render_template, url_for
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
#from flask_api import status
from werkzeug.utils import secure_filename

# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINT
##############################
#ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'fits'])

def allowed_file(filename):
	#return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['UPLOAD_ALLOWED_FILE_FORMATS']

upload_bp = Blueprint('upload', __name__, url_prefix='/caesar/api/v1.0')
#upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload', methods=['POST'])
def upload_file():
	""" Upload image """

	logger.info("request.url=%s" % request.url)
	
	# - Init response
	res= {
		'filename_orig': '',
		'format': '',
		'size': '',
		'uuid': '',
		'path': '',
		'date': '',
		'status': ''
	}
	
	# - Check this is a POST request
	#if not request.method == 'POST':
	#	flash('This request is not POST as required')
	#	logger.error("This request is not POST as required")
	#	#return redirect(request.url)
	#	res['status']= 'This request is not POST as required'
	#	return make_response(jsonify(res),400)

	# - Check for file
	if 'file' not in request.files:
		flash('No file part')
		logger.error("This request has no file part!")
		res['status']= 'Request has no file part'
		return make_response(jsonify(res),400)
		#return redirect(request.url)
		
	f = request.files['file']
	if not f:
		flash('No file retrieved from request!')
		logger.error("No file retrieved from request!")
		res['status']= 'No file retrieved from request'
		return make_response(jsonify(res),400)
		#return redirect(request.url)

	if f.filename == '':
		flash('No file selected for uploading')
		logger.error("No file selected for uploading!")
		res['status']= 'No file selected for uploading'
		return make_response(jsonify(res),400)
		#return redirect(request.url)

	if not allowed_file(f.filename):
		flash('File format not allowed, allowed file types are: {png, jpg, jpeg, gif}')
		logger.error("File format not allowed, allowed file types are: {png, jpg, jpeg, gif}")
		res['status']= 'File format not allowed, allowed types are {png|jpg|jpeg|gif|fits}'
		return make_response(jsonify(res),415)
		#return redirect(request.url)

	filename= secure_filename(f.filename)
	file_ext= os.path.splitext(filename)[1].split('.')[1]
	file_uuid= uuid.uuid4().hex
	filename_dest= '.'.join([file_uuid,file_ext])
	filename_dest_fullpath= os.path.join(current_app.config['UPLOAD_FOLDER'], filename_dest)
	
	# - Save file
	logger.info("Saving file %s ..." % filename_dest_fullpath)
	f.save(filename_dest_fullpath)
	flash('File successfully uploaded')

	# - Set file info
	now = datetime.datetime.now()
	file_upload_date= now.isoformat()
	file_size= os.path.getsize(filename_dest_fullpath)/(1024.*1024.) # in MB

	res['filename_orig']= filename
	res['format']= file_ext
	res['size']= file_size
	res['uuid']= file_uuid
	res['path']= filename_dest_fullpath
	res['date']= file_upload_date
	res['status']= 'File uploaded with success'

	# - Register file in DB
	try:
		current_app.config['datamgr'].register_file(filename_dest_fullpath)
		flash('File registered with success')
		logger.info("File registered with success")
	except:
		flash('File uploaded but failed to be registered!')
		res['status']= 'File uploaded but failed to be registered'
		return make_response(jsonify(res),500)
		#return redirect(request.url)
	
	#return redirect('/')
	return make_response(jsonify(res),200)	
