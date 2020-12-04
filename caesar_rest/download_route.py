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
from flask import current_app, Blueprint, render_template, request, redirect, url_for, g
from flask import send_file, send_from_directory, safe_join, abort, make_response, jsonify
from werkzeug.utils import secure_filename
from caesar_rest import oidc
from caesar_rest.decorators import custom_require_login
from caesar_rest import mongo
from caesar_rest import logger
from caesar_rest.config import Config
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
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info): 
		username=g.oidc_token_info['email']

	# - Get all file uuids
	res= {}
	collection_name= username + '.files'
	try:
		data_collection= mongo.db[collection_name]
		file_cursor= data_collection.find({},projection={"_id":0, "filepath":0})
		res = list(file_cursor)
	except Exception as e:
		errmsg= 'Exception caught when getting file ids from DB (err=' + str(e) + ')!'
		logger.error(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)

	return make_response(jsonify(res),200)
	


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
	username= 'anonymous'
	if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
		username=g.oidc_token_info['email']

	# - Search file uuid
	collection_name= username + '.files'
	item= None
	try:
		data_collection= mongo.db[collection_name]
		##item= data_collection.find_one({'_id': ObjectId(file_uuid)})
		item= data_collection.find_one({'fileid': str(file_uuid)})

	except Exception as e:
		errmsg= 'Exception caught when searching file in DB (err=' + str(e) + ')!'
		logger.error(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)
		
	if item and item is not None:
		file_path= item['filepath']
		logger.info("File with uuid=%s found at path=%s ..." % (file_uuid, file_path))
	else:
		logger.warn("File with uuid=%s not found in DB!" % file_uuid)
		file_path= ''
	
	if not file_path or file_path=='':
		errmsg= 'File with uuid ' + file_uuid + ' not found on the system!'
		logger.warn(errmsg)
		res['status']= errmsg
		return make_response(jsonify(res),404)
		
	# - Return file to client	
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


