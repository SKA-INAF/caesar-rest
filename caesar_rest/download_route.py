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

# Import flask modules
from flask import current_app, Blueprint, render_template, request, redirect, url_for
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
from werkzeug.utils import secure_filename
from caesar_rest import oidc
from caesar_rest.decorators import custom_require_login
from caesar_rest import mongo
from bson.objectid import ObjectId

# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINTS
##############################
download_id_bp = Blueprint('download_id', __name__,url_prefix='/caesar/api/v1.0')
fileids_bp = Blueprint('fileids', __name__, url_prefix='/caesar/api/v1.0')

# - Returns all file ids registered in the system
@fileids_bp.route('/fileids', methods=['GET'])
@custom_require_login
def get_registered_file_ids():
	""" Returns all file ids registered in the system """
	
	# - Get aai info
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

	# - Get mongo info
	mongo_enabled= current_app.config['USE_MONGO']
	has_mongo= (mongo is not None)
	use_mongo= (mongo_enabled and has_mongo)

	# - Get all file uuids
	d= {}	
	if use_mongo:
		data_collection= mongo.db[username]
		file_ids= data_collection.find().distinct('_id')		
		file_id_list= [str(fileid) for fileid in file_ids]
		d.update({'file_ids':file_id_list})

	else:
		file_ids= current_app.config['datamgr'].get_file_ids()		
		d.update({'file_ids':file_ids})

	return make_response(jsonify(d),200)
	


# - Download data by uuid
@download_id_bp.route('/download', methods=['GET', 'POST'])
@custom_require_login
def download_id():
	""" Download data by uuid """
	if request.method == 'POST':
		uuid = request.form['uuid']
	else:
		uuid = request.args.get('uuid')

	logger.info("uuid: %s" % uuid)
	return redirect(url_for('download_id.download_by_uuid',file_uuid=uuid))


@download_id_bp.route('/download/<string:file_uuid>', methods=['GET', 'POST'])
@custom_require_login
def download_by_uuid(file_uuid):
	""" Download data by uuid """

	# - Init response
	res= {
		'status': ''
	}

	# - Get aai info
	aai_enabled= current_app.config['USE_AAI']
	has_oidc= (oidc is not None)
	username= 'anonymous'
	if aai_enabled and has_oidc:
		username= oidc.user_getfield('preferred_username')

	# - Get mongo info
	mongo_enabled= current_app.config['USE_MONGO']
	has_mongo= (mongo is not None)
	use_mongo= (mongo_enabled and has_mongo)

	# Search file uuid
	if use_mongo:
		data_collection= mongo.db[username]
		item= data_collection.find_one({'_id': ObjectId(file_uuid)})
		if item:
			file_path= item['filepath']
			logger.info("File with uuid=%s found at path=%s ..." % (file_uuid, file_path))
		else:
			logger.warn("File with uuid=%s not found in DB!" % file_uuid)
			file_path= ''
	else:	
		file_path= current_app.config['datamgr'].get_filepath(file_uuid)

	if not file_path or file_path=='':
		errmsg= 'File with uuid ' + file_uuid + ' not found on the system!'
		logger.warn(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)
		
	# Return file to client	
	logger.info("Returning file %s to client ..." % file_path)
	try:
		return send_file(
			file_path, 
			as_attachment=True
		)
	except FileNotFoundError:
		errmsg= 'File with uuid ' + file_uuid + ' not found on the system!'
		logger.warn(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)


