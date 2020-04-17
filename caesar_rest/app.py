
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

logger.info("Module __name__: %s " % __name__)
logger.info("Module __package__: %s " % __package__)





ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'fits'])

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


##############################
#   APP CREATION CLASS
##############################
logger.info("Creating Flask app using default config settings ...")

app = Flask(__name__, instance_relative_config=True)
#app = Flask(__name__)
app.config.from_object(Config())


##############################
#   APP ENDPOINTS
##############################
# - Base entry point
#@app.route('/')
#def index():
#	""" App entry point """
#	return "Hello, World!"

@app.route('/')
def index():
	return render_template('index.html')

# - Upload image
@app.route('/upload', methods=['POST'])
#@app.route('/', methods=['POST'])
def upload_file():
	""" Upload image """
	if request.method == 'POST':
		# Check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		
		f = request.files['file']
		
		if f.filename == '':
			flash('No file selected for uploading')
			return redirect(request.url)

		if f and allowed_file(f.filename):
			filename = secure_filename(f.filename)
			f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
			flash('File successfully uploaded')
			return redirect('/')
		else:
			flash('Allowed file types are: {png, jpg, jpeg, gif}')
			return redirect(request.url)

# - Download data by file name
@app.route('/download', methods=['GET', 'POST'])
def download():
	""" Download data by path (only for testing) """
	if request.method == 'POST':
		filename = request.form['filename']
	else:
		filename = request.args.get('filename')

	logger.info("download filename: %s" % filename)
	return redirect(url_for('download_by_name',filename=str(filename)))


@app.route('/download/<string:filename>', methods=['GET', 'POST'])
def download_by_name(filename):
	""" Download data by path (only for testing) """
	try:
		return send_from_directory(
			directory=app.config['UPLOAD_FOLDER'], 
			filename=filename, 
			as_attachment=True
		)
	except FileNotFoundError:
		abort(404)




# - Download data by uuid
@app.route('/download/<uuid:file_uuid>', methods=['GET', 'POST'])
def download_by_uuid(file_uuid):
	""" Download data by uuid """

	# Search file uuid
	# ...
	file_path= ''

	# Return file to client
	try:
		return send_file(
			file_path, 
			as_attachment=True
		)
	except FileNotFoundError:
		abort(404)

