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
from flask import send_file, send_from_directory, safe_join, abort
from werkzeug.utils import secure_filename

# Get logger
logger = logging.getLogger(__name__)


##############################
#   CREATE BLUEPRINTS
##############################
#download_path_bp = Blueprint('download_path', __name__)
#download_id_bp = Blueprint('download_id', __name__)
download_path_bp = Blueprint('download_path', __name__,url_prefix='/caesar/api/v1.0')
download_id_bp = Blueprint('download_id', __name__,url_prefix='/caesar/api/v1.0')


# - Download data by file name
@download_path_bp.route('/download-path', methods=['GET', 'POST'])
def download_path():
	""" Download data by path (only for testing) """
	if request.method == 'POST':
		filename = request.form['filename']
	else:
		filename = request.args.get('filename')

	#logger.info("download filename: %s" % filename)
	return redirect(url_for('download_path.download_by_name',filename=str(filename)))


@download_path_bp.route('/download-path/<string:filename>', methods=['GET', 'POST'])
def download_by_name(filename):
	""" Download data by path (only for testing) """
	try:
		return send_from_directory(
			directory=current_app.config['UPLOAD_FOLDER'], 
			filename=filename, 
			as_attachment=True
		)
	except FileNotFoundError:
		abort(404)


# - Download data by uuid
@download_id_bp.route('/download-id', methods=['GET', 'POST'])
def download_id():
	""" Download data by uuid """
	if request.method == 'POST':
		uuid = request.form['uuid']
	else:
		uuid = request.args.get('uuid')

	logger.info("uuid: %s" % uuid)
	return redirect(url_for('download_id.download_by_uuid',file_uuid=uuid))

#@download_id_bp.route('/download/<uuid:file_uuid>', methods=['GET', 'POST'])
@download_id_bp.route('/download-id/<string:file_uuid>', methods=['GET', 'POST'])
def download_by_uuid(file_uuid):
	""" Download data by uuid """

	# Search file uuid
	file_path= current_app.config['datamgr'].get_filepath(file_uuid)
	if not file_path:
		logger.warn("File with uuid=%s not found on the system!" % file_uuid)
		raise FileNotFoundError("File with given uuid not found on the system")

	# Return file to client	
	logger.info("Returning file %s to client ..." % file_path)
	try:
		return send_file(
			file_path, 
			as_attachment=True
		)
	except FileNotFoundError:
		abort(404)

