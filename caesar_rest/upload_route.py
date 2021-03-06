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
from flask import current_app, Blueprint, flash, request, redirect, render_template, url_for, g
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
#from flask_api import status
from werkzeug.utils import secure_filename
from caesar_rest import oidc
from caesar_rest.decorators import custom_require_login
#from caesar_rest import db
#from caesar_rest.data_model import DataFile #, DataCollection 
from caesar_rest import mongo

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

@upload_bp.route('/upload', methods=['POST'])
@custom_require_login
def upload_file():
	""" Upload image """

	logger.info("request.url=%s" % request.url)

	# - Get aai info
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		username=g.oidc_token_info['email']

	# - Init response
	res= {
		'filename_orig': '',
		'tag': '',
		'format': '',
		'size': '',
		'uuid': '',
		#'path': '',
		'date': '',
		'status': ''
	}
	
	# - Check for file
	logger.info("Checking for file key in request ...")
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
	filename_dest_dir= current_app.config['UPLOAD_FOLDER'] + '/' + str(username)
	#filename_dest_fullpath= os.path.join(current_app.config['UPLOAD_FOLDER'], filename_dest)
	filename_dest_fullpath= os.path.join(filename_dest_dir, filename_dest)
	
	file_tag = ''
	if request.form:
		if 'tag' in request.form:
			file_tag= request.form['tag']
		else:
			logger.info("No tag information given in request, set empty...")
	else:
		logger.warn("form not present in request...")

	# - Create username directory if not existing before
	logger.info("Creating username directory if not existing before ...")
	try: 
		os.makedirs(filename_dest_dir)
	except OSError:
		if not os.path.isdir(filename_dest_dir):
			flash('Failed to create file destination dir for user!')
			logger.warn("Failed to create file destination dir for user %s!" % username)
			res['status']= 'Failed to create file destination dir for user!'
			return make_response(jsonify(res),500)
	
	# - Save file
	logger.info("Saving file %s ..." % filename_dest_fullpath)
	f.save(filename_dest_fullpath)
	flash('File successfully uploaded')

	# - Set file info
	now = datetime.datetime.now()
	file_upload_date= now.isoformat()
	file_size= os.path.getsize(filename_dest_fullpath)/(1024.*1024.) # in MB

	res['filename_orig']= filename
	res['tag'] = file_tag
	res['format']= file_ext
	res['size']= file_size
	res['uuid']= file_uuid
	#res['path']= filename_dest_fullpath # removed for security reasons
	res['date']= file_upload_date
	res['status']= 'File uploaded with success'

	# - Register file in MongoDB
	logger.info("Creating data file object ...")
	data_fileobj= {
		"filepath": filename_dest_fullpath,
		"fileid": file_uuid,
		"filename_orig": filename,
		"fileext": file_ext,	
		"filesize": file_size,
		"filedate": file_upload_date, 
		"metadata": '', # FIX ME
		"tag": file_tag
	}

	collection_name= username + '.files'
		
	try:			
		logger.info("Creating or retrieving data collection %s for user %s ..." % (collection_name, username))
		data_collection= mongo.db[collection_name]

		logger.info("Adding data file obj to collection ...")
		item_id= data_collection.insert(data_fileobj)
		#res['uuid']= str(item_id)
		
	except Exception as e:
		logger.warn("Failed to create and register data file in DB (err=%s)!" % str(e))
		flash('File uploaded but failed to be registered in DB!')
		logger.warn("File %s uploaded but failed to be registered in DB (err=%s)!" % (filename_dest_fullpath,str(e)))
		res['status']= 'File uploaded but failed to be registered in DB'
		return make_response(jsonify(res),500)

	return make_response(jsonify(res),200)

