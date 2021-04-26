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
import subprocess

# Import astro modules
from astropy.io import fits
from astropy.visualization import ZScaleInterval, LinearStretch, ImageNormalize, MinMaxInterval
import regions
from regions import DS9Parser
from regions import read_ds9

## Graphics modules
import matplotlib as mpl
mpl.rcParams['xtick.direction'] = 'in'
mpl.rcParams['ytick.direction'] = 'in'

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


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

def get_dir_size(dirname,unit='K'):
	""" Return the directory size in specified units """
		
	cmd= 'du'
	cmd_args= '-shB' + unit
	dirsize_str= subprocess.check_output([cmd,cmd_args, dirname]).split()[0].decode('utf-8')
	dirsize= float(dirsize_str.replace(unit,''))
	return dirsize


def plot_img_and_regions(imgfile, regionfiles=[], zmin=0, zmax=0, cmap="afmhot", contrast=0.3, save=False, outfile="plot.png"):
	""" Plot input FITS and regions """

	#===========================
	#==   READ REGION
	#===========================
	regs= []
	for regionfile in regionfiles:
		logger.info("Reading region file %s ..." % regionfile)
		region_list= regions.read_ds9(regionfile)
		regs.extend(region_list)

	#===========================
	#==   READ IMAGE
	#===========================
	# - Read fits
	try:
		hdu= fits.open(imgfile)
		data= hdu[0].data
		header= hdu[0].header
	except:
		logger.error("Failed to open input img %s!" % imgfile)
		return -1

	# - Remove 3 and 4 channels
	nchan= len(data.shape)
	logger.info("Input image has %d channels..." % nchan)
	if nchan==4:
		data= data[0,0,:,:]
	elif nchan==3:
		data= data[0,:,:]
	else:
		if nchan!=2:	
			logger.error("Invalid/unrecognized number of channels (%d)!" % nchan)
			return -1
		
	# - Get image units	
	bunit= 'z'
	if 'BUNIT' in header:
		bunit= header['BUNIT']

	# - Set stretch	
	stretch= LinearStretch()
	norm = ImageNormalize(data, interval=ZScaleInterval(contrast=contrast), stretch=stretch)
	
	#===========================
	#==   PLOT IMAGE
	#===========================
	# - Plot image	
	fig = plt.figure(figsize=(10,10))
	ax = fig.add_subplot(1, 1, 1)
	if zmin<zmax:
		im= ax.imshow(data, origin='lower', vmin=zmin, vmax=zmax, cmap=cmap, norm=norm)
	else:
		im= ax.imshow(data, origin='lower', cmap=cmap, norm=norm)
	
	# - Set axis titles
	ax.set_xlabel('x',size=18, labelpad=0.7)
	ax.set_ylabel('y',size=18)

	# - Draw color bar
	color_bar_label= 'Brightness (' + bunit + ')'
	cb= fig.colorbar(im, orientation="vertical", pad=0.01, fraction=0.047)
	cb.set_label(color_bar_label, y=1.0, ha='right',size=12)
	cb.ax.tick_params(labelsize=12) 

	# - Set ticks
	plt.tick_params(axis='x', labelsize=14)
	plt.tick_params(axis='y', labelsize=14)

	# - Superimpose regions
	region_color= "lime"
	region_style= "dashed"
	#region_style= "solid"

	if regionfile!="":
		logger.debug("Superimposing region ...")
		for r in regs:
			r.plot(ax=ax, color=region_color, linestyle=region_style)
	
	# - Save or display
	if save:
		plt.savefig(outfile, bbox_inches='tight')
	else:
		plt.show()

	return 0




