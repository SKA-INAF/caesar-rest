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
import hashlib
import tarfile

# Get logger
logger = logging.getLogger(__name__)


def tarsum(input_filename, output_filename, hash_type='md5'):
	"""
		input_file  - A FILE object to read the tar file from.
		hash - The name of the hash to use. Must be supported by hashlib.
		output_file - A FILE to write the computed signatures to.
	"""

	# - Open tar file
	try:
		#tar= tarfile.open(mode="r|*", fileobj=input_file)
		tar= tarfile.open(name=input_filename,mode='r|*')
	except Exception as e:
		logger.error("Failed to open tar file %s (err=%s)!" % (input_file,e))
		return -1		

	# - Open output file
	output_file = open(output_filename, "w")

	# - Compute checksums for all files and write to output file
	chunk_size = 100*1024
	store_digests = {}
 
	for item in tar:
		if not item.isfile():
			continue
		f = tar.extractfile(item)
		h = hashlib.new(hash_type)
		data = f.read(chunk_size)
		while data:
			h.update(data)
			data = f.read(chunk_size)

		output_file.write("%s  %s\n" % (h.hexdigest(), item.name))

	return 0


def make_tar(output_filename, source_dir):
	""" Create a tar file """
	with tarfile.open(output_filename, "w:gz") as tar:
		tar.add(source_dir, arcname=os.path.basename(source_dir))

def sanitize_username(s):
	""" Sanitize username removing @ and . and replacing with underscores """

	username= s.replace('@', '_')
	username= username.replace('.', '_')

	return username





