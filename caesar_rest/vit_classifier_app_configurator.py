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
#   ViT CLASSIFIER APP CONFIGURATOR
##########################################

class ViTClassifierAppConfigurator(AppConfigurator):
	""" Class to configure ViT image classifier application """

	def __init__(self, app_name="classifier-vit"):
		""" Return aapp configurator class """
		AppConfigurator.__init__(self, app_name=app_name)

		# - Define cmd name
		self.cmd= 'run_classifier.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Describe app
		self.description = (
			"Run a pre-trained vision transformer (ViT) classifier model on astronomical radio-continuum images to predict class label. "
			"The app supports different classifier models, described below: \n\n",
			"* 'smorphclass_multilabel': Multi-label multi-class classification of radio images into one or more of these six possible classes: \n"
			"    - BACKGROUND: if image is purely background noise, e.g. no sources are visible, like for image frames located at the map borders\n"
			"    - RADIO-GALAXY: if any extended source is visible with a single- or multi-island morphology, suggesting that of a radio galaxy\n"
			"    - DIFFUSE: if any diffuse source is visible, typically having small-scale (e.g. <few arcmin) and roundish morphology\n"
			"    - DIFFUSE-LARGE:  if any large-scale (e.g. covering half of the image) diffuse object with irregular shape is visible\n"
			"    - ARTEFACT: if any ring-shaped or ray-like artefact is visible, e.g. typically around bright resolved source\n"
			"    This classifier aims to detect the presence of objects with a given morphology in input images with a larger field of view (~few arcmin, typically >128x128 pixels) and not on image cutouts zoomed in around a specific source.\n"
			"* 'smorphclass_singlelabel_rgz': Single-label multi-class classification of radio images into one of these six possible morphological classes: \n"
			"    - 1C-1P: single-island source having only one flux intensity peak\n"
			"    - 1C-2P: single-island source having two flux intensity peaks\n"
			"    - 1C-3P: single-island source having three flux intensity peaks\n"
			"    - 2C-2P: source formed by two disjoint islands, each hosting a single flux intensity peak\n"
			"    - 2C-3P: source formed by two disjoint islands, where one has a single flux intensity peak and the other one has two intensity peaks\n"
			"    - 3C-3P: source formed by three disjoint islands, each hosting a single flux intensity peak\n"
			"    The labelling schema is taken from the Radio Galaxy Zoo (RGZ) project, where 'C' stands for source 'components', while 'P' for 'peaks'. This classifier is intended to be run on images zoomed in around a source, typically having original size <128x128 pixels."
		)
		
		
		self.input_requirements = {
			"supported_formats": ["fits", "png"],
			"expected_data": "Single astronomical image suitable for source classification. The image is expected to be centred and zoomed-in on a source for some classification tasks/models ('smorphclass_singlelabel_rgz') or having a larger field of view and including more than one source for other classification tasks ('smorphclass_multilabel')",
			"notes": [
				"The method is most suited for radio-continuum images."
			]
		}
		
		self.limitations = [
			"The app is for source classification only, NOT for source detection (e.g. not providing any bounding box or segmentation mask).",
			"Classification accuracy depends on the selected pretrained model, image preprocessing, survey parameters (e.g. resolution/noise) and size of the input image.",
			"The app can in principle be used to classify sources in astronomical images (FITS/PNG) from other domains (e.g. optical, infrared, gamma-rays) but we anticipate sub-optimal performance as the model was trained/tested on radio images only."
		]
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			# == MODEL OPTIONS ==
			'model' : EnumValueOption(
				name='model',
				value='',
				value_type=str, 
				description='Classifier model to be used. See app description.',
				category='MODEL',
				default_value='smorphclass_multilabel',
				allowed_values=['smorphclass_multilabel', 'smorphclass_singlelabel_rgz']
			),

			# == PRE-PROCESSING OPTIONS ==
			'zscale' : Option(
				name='zscale', 
				description='Apply z-scale transform with given contrast', 
				category='PREPROCESSING',
				default_value=True
			),
			'zscale-contrast' : ValueOption(
				name='zscale-contrast',
				value='',
				value_type=float, 
				description='zscale contrast applied to all channels',
				category='PREPROCESSING',
				default_value=0.25
			),
			
			# == RUN OPTIONS ==
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN',
				default_value=False
			),
			
		
		} ## close valid options
		
		# - Define dictionary with job outputs produced
		catalog_out_desc= (
			'Dictionary containing image classification labels (depending on classification task/model) and relative probability/confidence score. '
			'When the input data is an image, the format of the returned dictionary follows the structure of the example below for multi-label classification tasks: \n\n'
			'{\n'		
			'  "filepath": "f572b6faffb34f5680bccb12c02aacf5.fits",\n'
			'  "sname": "f572b6faffb34f5680bccb12c02aacf5",\n'
			'  "label_pred": ["RADIO-GALAXY", "EXTENDED"],\n'
			'  "prob_pred": [0.606,0.754]\n'
			'}\n'
			'\n'
			'In the case of single-label classification task, the returned dictionary follows the structure below:\n\n'
			'{\n'		
			'  "filepaths": "f572b6faffb34f5680bccb12c02aacf5.fits",\n'
			'  "sname": "f572b6faffb34f5680bccb12c02aacf5",\n'
			'  "label_pred": "1C-1P",\n'
			'  "prob_pred": 0.85\n'
			'}\n'
			'\n'
			'Below, we report a description of each dictionary field: \n'
			'* filepath | str: Input image filename (base path, not absolute path).\n'
			'* sname | str: Input image identifier, usually set to filepath without file extension.\n'
			'* label_pred | str or List[str]: Predicted classification label for single-label class tasks, or list of labels for multi-label class tasks\n'
			'* prob_pred | float or List[float]: Classification probability for predicted class label in single-label class tasks, or list of probabilities for each predicted label in multi-label class tasks'
		)
		
		self.job_outputs= {
			"catalog": {
				"path": None,
				"glob": "classifier_results.json",
				"type": "application/json",
				"role": "primary_result",
				"description": catalog_out_desc,
				"parser": "json",
				"required": True,
				"notes": (
					""
				)
			},
			"log": {
				"path": None,
				"glob": "*.log",
				"type": "text/plain",
				"role": "diagnostic",
				"description": "Execution logs.",
				"parser": "text",
				"required": False,
				"notes": (
					""
				)
		}
		
		# - Define option value transformers
		self.option_value_transformer= {
		
		
		} 
		
		# - Fill some default cmd args
		logger.debug("Adding some options by default ...", action="submitjob")
		self.cmd_args.append("--run")
		self.cmd_args.append("--save-base-path") # do not expose internal paths to clients
		
	def set_data_input_option_value(self):
		""" Set app input option value """

		input_opt= "".join("--inputfile=%s" % self.data_inputs)
		self.cmd_args.append(input_opt)
		
