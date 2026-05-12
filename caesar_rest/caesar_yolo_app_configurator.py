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
import subprocess
import json
import ast
import yaml

# Import flask modules
from flask import current_app, g

# Import caesare rest modules
from caesar_rest import oidc
from caesar_rest import mongo
from caesar_rest import utils
from caesar_rest.base_app_configurator import AppConfigurator
from caesar_rest.base_app_configurator import Option, ValueOption, EnumValueOption

# Get logger
from caesar_rest import logger

##########################################
#   CAESAR-YOLO APP CONFIGURATOR
##########################################

class CaesarYoloAppConfigurator(AppConfigurator):
	""" Class to configure caesar-yolo source finder application """

	def __init__(self, app_name="caesar-yolo"):
		""" Return app configurator class """
		AppConfigurator.__init__(self, app_name=app_name)

		# - Define cmd name
		self.cmd= 'run_sdetector.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Describe app
		self.description = (
			"Run YOLO-based object detection on astronomical radio-continuum images. "
			"The app detects candidate radio sources and classifies them as spurious, compact, "
			"extended, extended-multisland, or flagged. It expects image-like astronomical data, "
			"typically FITS-derived image products or CAESAR-supported image inputs. "
			"Results are returned as a JSON catalog of detections and optional diagnostic plots."
		)
		
		self.input_requirements = {
			"supported_formats": ["uid", "abspath", "dataset"],
			"expected_data": "Single astronomical image suitable for source/object detection.",
			"notes": [
				"Use uid input in production after uploading the file to caesar-rest.",
				"Use abspath only when MAASAI and caesar-rest share the same filesystem.",
				"Use dataset only for datasets registered in the CAESAR service."
			]
		}

		self.limitations = [
			"Detection quality depends on the selected pretrained model and image preprocessing.",
			"Bounding boxes are image-pixel coordinates, not sky coordinates unless post-processed with WCS metadata.",
			"Very large images may require tiling.",
			"Low-confidence detections depend strongly on score-thr and preprocessing choices."
		]
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			# == MODEL OPTIONS ==
			'model' : EnumValueOption(
				name='model',
				value='',
				value_type=str, 
				description='Pretrained model to be used in prediction',
				category='MODEL',
				default_value='yolov11l_imgsize640',
				allowed_values=['yolov11l_imgsize128','yolov11l_imgsize256','yolov11l_imgsize512','yolov11l_imgsize640']
			),

			# == PRE-PROCESSING OPTIONS ==
			'xmin' : ValueOption(
				name='xmin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel x=xmin (-1: read full image)',
				category='IMGREAD',
				default_value=-1,
				min_value=-1000000,
				max_value=1000000
			),
			'xmax' : ValueOption(
				name='xmax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel x=xmax (-1: read full image)',
				category='IMGREAD',	
				default_value=-1,
				min_value=-1000000,
				max_value=1000000
			),
			'ymin' : ValueOption(
				name='ymin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel y=xmin (-1: read full image)',
				category='IMGREAD',	
				default_value=-1,
				min_value=-1000000,
				max_value=1000000
			),
			'ymax' : ValueOption(
				name='ymax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel y=ymax (-1: read full image)',
				category='IMGREAD',
				default_value=-1,
				min_value=-1000000,
				max_value=1000000
			),
			'imgsize' : ValueOption(
				name='imgsize',
				value='',
				value_type=int, 
				description='Image resize in pixels',
				category='PREPROCESSING',
				default_value=640,
				min_value=16,
				max_value=1024
			),
			'preprocessing' : Option(
				name='preprocessing', 
				description='Apply pre-processing to input image',
				category='PREPROCESSING'
			),
			'normalize' : Option(
				name='normalize', 
				description='Normalize each channel in range', 
				category='PREPROCESSING'
			),
			'normmin' : ValueOption(
				name='normmin',
				value='',
				value_type=float, 
				description='Normalization min value',
				category='PREPROCESSING',
				default_value=0.0,
				min_value=-1.0,
				max_value=0.0
			),
			'normmax' : ValueOption(
				name='normmax',
				value='',
				value_type=float, 
				description='Normalization max value',
				category='PREPROCESSING',
				default_value=1.0,
				min_value=1.0,
				max_value=255.0
			),
			'subtract_bkg' : Option(
				name='subtract_bkg', 
				description='Subtract bkg from ref channel image', 
				category='PREPROCESSING'
			),
			'sigma-bkg' : ValueOption(
				name='sigma-bkg',
				value='',
				value_type=float, 
				description='Sigma clip to be used in bkg calculation',
				category='PREPROCESSING',
				default_value=3.0,
				min_value=1.0,
				max_value=100.0
			),
			'subtract-bkg' : Option(
				name='subtract-bkg', 
				description='Subtract bkg from ref channel image', 
				category='PREPROCESSING'
			),
			'use-box-mask-in-bkg' : Option(
				name='use-box-mask-in-bkg', 
				description='Compute bkg value in borders left from box mask', 
				category='PREPROCESSING'
			),
			'bkg-box-mask-fract' : ValueOption(
				name='bkg-box-mask-fract',
				value='',
				value_type=float, 
				description='Size of mask box dimensions with respect to image size used in bkg calculation',
				category='PREPROCESSING',
				default_value=0.7,
				min_value=0.0001,
				max_value=1.0
			),
			'bkg-chid' : ValueOption(
				name='bkg-chid',
				value='',
				value_type=int, 
				description='Channel to subtract background (-1=all)',
				category='PREPROCESSING',
				default_value=-1,
				min_value=-1,
				max_value=3
			),
			'clipshiftdata' : Option(
				name='clipshiftdata', 
				description='Do sigma clipping shifting', 
				category='PREPROCESSING'
			),
			'sigmaclip' : ValueOption(
				name='sigmaclip',
				value='',
				value_type=float, 
				description='Sigma threshold to be used for clip & shifting pixels',
				category='PREPROCESSING',
				default_value=1.0,
				min_value=0.001,
				max_value=100
			),
			'clipdata' : Option(
				name='clipdata', 
				description='Apply sigma clipping to all channels', 
				category='PREPROCESSING'
			),
			'sigmaclip-low' : ValueOption(
				name='sigmaclip-low',
				value='',
				value_type=float, 
				description='Lower sigma threshold to be used for clipping pixels below (mean-sigma_low*stddev)',
				category='PREPROCESSING',
				default_value=10.0,
				min_value=0.001,
				max_value=100
			),
			'sigmaclip-up' : ValueOption(
				name='sigmaclip-up',
				value='',
				value_type=float, 
				description='Upper sigma threshold to be used for clipping pixels above (mean+sigma_up*stddev)',
				category='PREPROCESSING',
				default_value=10.0,
				min_value=0.001,
				max_value=100
			),
			'sigmaclip-chid' : ValueOption(
				name='sigmaclip-chid',
				value='',
				value_type=int, 
				description='Channel to clip data (-1=all)',
				category='PREPROCESSING',
				default_value=-1,
				min_value=-1,
				max_value=3
			),		
			'zscale' : Option(
				name='zscale', 
				description='Apply z-scale transform to each channel with given contrasts', 
				category='PREPROCESSING'
			),
			'zscale-contrasts' : ValueOption(
				name='zscale-contrasts',
				value='',
				value_type=str, 
				description='zscale contrasts applied to all channels, separated by commas',
				category='PREPROCESSING',
				default_value='0.25,0.25,0.25'
			),
			'chan3-preproc' : Option(
				name='chan3-preproc', 
				description='Use the 3-channel pre-processor', 
				category='PREPROCESSING'
			),
			'sigmaclip-baseline' : ValueOption(
				name='sigmaclip-baseline',
				value='',
				value_type=float, 
				description='Lower sigma threshold to be used for clipping pixels below (mean-sigma_low*stddev) in first channel of 3-channel preprocessing',
				category='PREPROCESSING',
				default_value=0.0
			),
			'nchans' : ValueOption(
				name='nchans',
				value='',
				value_type=int, 
				description='Number of channels. If you modify channels in preprocessing you must set this accordingly',
				category='PREPROCESSING',
				default_value=1,
				min_value=1,
				max_value=3
			),
			
			# == DETECT OPTIONS ==
			'score-thr' : ValueOption(
				name='score-thr',
				value='',
				value_type=float, 
				description='Object detection score threshold to be used during test',
				category='DETECT',
				default_value=0.7,
				min_value=0.0,
				max_value=1.0
			),
			'iou-thr' : ValueOption(
				name='iou-thr',
				value='',
				value_type=float, 
				description='Intersection Over Union (IoU) threshold for Non-Maximum Suppression (NMS)',
				category='DETECT',
				default_value=0.5,
				min_value=0.0,
				max_value=1.0
			),
			'merge-overlap-iou-thr-soft' : ValueOption(
				name='merge-overlap-iou-thr-soft',
				value='',
				value_type=float, 
				description='IOU threshold used to merge overlapping detected objects with same class ',
				category='DETECT',
				default_value=0.3,
				min_value=0.0,
				max_value=1.0
			),
			'merge_overlap-iou-thr-hard' : ValueOption(
				name='merge_overlap-iou-thr-hard',
				value='',
				value_type=float, 
				description='IOU threshold used to merge overlapping detected objects, even those with same class ',
				category='DETECT',
				default_value=0.8,
				min_value=0.0,
				max_value=1.0
			),
	
			# == PARALLEL RUN OPTIONS ==
			'split-img-in-tiles' : Option(
				name='split-img-in-tiles', 
				description='Split input image in multiple sub tiles', 
				category='PARALLEL-RUN'
			),
			'tile-xsize' : ValueOption(
				name='tile-xsize',
				value='',
				value_type=int, 
				description='Sub image size in pixel along x',
				category='PARALLEL-RUN',
				default_value=512,
				min_value=16,
				max_value=1024
			),
			'tile-ysize' : ValueOption(
				name='tile-ysize',
				value='',
				value_type=int, 
				description='Sub image size in pixel along y',
				category='PARALLEL-RUN',
				default_value=512,
				min_value=16,
				max_value=1024
			),
			'tile-xstep' : ValueOption(
				name='tile-xstep',
				value='',
				value_type=float, 
				description='Sub image step fraction along x (=1 means no overlap)',
				category='PARALLEL-RUN',
				default_value=1.0,
				min_value=0.0,
				max_value=1.0
			),
			'tile-ystep' : ValueOption(
				name='tile-ystep',
				value='',
				value_type=float, 
				description='Sub image step fraction along y (=1 means no overlap)',
				category='PARALLEL-RUN',
				default_value=1.0,
				min_value=0.0,
				max_value=1.0
			),
			'max-ntasks-per-worker' : ValueOption(
				name='max-ntasks-per-worker',
				value='',
				value_type=int, 
				description='Max number of tasks assigned to a MPI processor worker',
				category='PARALLEL-RUN',
				default_value=100,
				min_value=1,
				max_value=200
			),
	
			# == DRAW OPTIONS ==
			'draw-plots' : Option(
				name='draw-plots', 
				description='Enable plot making', 
				category='DRAW'
			),
			'draw-class-label-in-caption' : Option(
				name='draw-class-label-in-caption', 
				description='Enable drawing of class label in plots', 
				category='DRAW'
			),
	
			# == SAVE OPTIONS ==
			'save-plots' : Option(
				name='save-plots', 
				description='Enable plot saving', 
				category='SAVE'
			),
			'save-tile-catalog' : Option(
				name='save-tile-catalog', 
				description='Enable saving of subtile catalog files', 
				category='SAVE'
			),
			'save-tile-region' : Option(
				name='save-tile-region', 
				description='Enable saving of subtile DS9 region files', 
				category='SAVE'
			),
			'save-tile-img' : Option(
				name='save-tile-img', 
				description='Enable saving of subtile image files', 
				category='SAVE'
			),
			'outfile-plot' : ValueOption(
				name='outfile-plot',
				value='',
				value_type=str, 
				description='Output plot PNG filename (internally generated if left empty)',
				category='SAVE',
				default_value='plot.png'
			),
			'outfile-catalog' : ValueOption(
				name='outfile-catalog',
				value='',
				value_type=str, 
				description='Output json filename with detected objects (internally generated if left empty for --image option)',
				category='SAVE',
				default_value='catalog.json'
			),
			'outfile-region' : ValueOption(
				name='outfile-region',
				value='',
				value_type=str, 
				description='Output DS9 region filename (internally generated if left empty)',
				category='SAVE',
				default_value='ds9.reg'
			),
	
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
			
		} ## close valid options
		
		
		# - Define dictionary with job outputs produced
		catalog_out_desc= (
			'Dictionary containing list of detected objects with class labels, scores, and bounding boxes. '
			'The format of the returned dictionary follows the example below: \n\n'
			'{\n'
			'  "filepath": "f572b6faffb34f5680bccb12c02aacf5", \n'
			'  "sname": "f572b6faffb34f5680bccb12c02aacf5", \n'
			'  "sources": [ \n'
			'    { \n'
			'      "class_id": 3, \n'
			'      "class_name": "extended-multisland", \n'
			'      "edge": 0, \n'
			'      "name": "S1", \n'
			'      "score": 0.8755874037742615, \n'
			'      "x1": 27.0, \n'
			'      "x2": 114.0, \n'
			'      "y1": 39.0, \n'
			'      "y2": 96.0 \n'
			'    } \n'
			'  ] \n'
			'} \n'
			'\n'
			'Below, we report a description of each dictionary field: \n'
			#'* filepath | str: Input image UID identifier, assigned by caesar-rest system.\n'
			'* filepath | str: Input image filename (not absolute filename).\n'
			'* sname | str: Input image identifier, usually set to filepath without file extension.\n'
			'* sources | list(dict): List of detected objects, with each object dictionary containing the following information: \n'
			'      - class_id | int: Object class identifier with these possible values: 0-->spurious, 1-->compact, 2-->extended, 3-->extended-multisland, 4-->flagged \n'
			'      - class_name | str: Object class label with these possible values: spurious, compact, extended, extended-multisland, flagged \n'
			'      - edge | int: Boolean flag indicating if the detected source is at the border (=1) of the image or not (=0) \n'
			'      - name | str: A string identifier for the detected object, usually with an "S" prefix followed by an integer \n'
			'      - score | float: Object detection confidence probability in range [0,1] \n'
			'      - x1 | float: Min x-axis coordinate of the object bounding box rectangle \n'
			'      - x2 | float: Max x-axis coordinate of the object bounding box rectangle \n'
			'      - y1 | float: Min y-axis coordinate of the object bounding box rectangle \n'
			'      - y2 | float: Max y-axis coordinate of the object bounding box rectangle \n'
		)
				
		self.job_outputs= {
			"catalog": {
				"path": None,
				"glob": "out_*.json",
				"type": "application/json",
				"role": "primary_result",
				"description": catalog_out_desc,
				"parser": "json",
				"required": True,
				"summary_hint": (
					"Summarize number of detected objects, class distribution, "
					"confidence-score range, edge flags, and bounding-box coordinates."
				),
			},
		
		} ## close job outputs
		
		# - Define option value transformers
		self.option_value_transformer= {
		
		
		} 
		
		# - Fill some default cmd args
		logger.debug("Adding some options by default ...", action="submitjob")
		self.cmd_args.append("--run")
		
	def set_data_input_option_value(self):
		""" Set app input option value """

		input_opt= "".join("--inputfile=%s" % self.data_inputs)
		self.cmd_args.append(input_opt)
		
