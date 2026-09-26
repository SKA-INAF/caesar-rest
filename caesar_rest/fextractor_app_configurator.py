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
#   FEAT EXTRACTOR APP CONFIGURATOR
##########################################
MODEL_CONTAINER_VARIANTS = {
	"simclr_radio": "tf",
	"dinov2": "torch",
	"dinov3": "torch",
	"dinov2_legacy": "torch",
	"siglip": "torch",
	"siglip2": "torch",
	"chronos2": "chronos",
}

class FeatExtractorAppConfigurator(AppConfigurator):
	""" Class to configure feature extractor application """

	def __init__(self, app_name="fextractor"):
		""" Return app configurator class """
		AppConfigurator.__init__(self, app_name=app_name)

		# - Define cmd name
		self.cmd= 'run_fextractor.sh'
		self.cmd_args= []
		self.batch_processing_support= True
		
		# - Describe app
		self.description = (
			"Extract fixed-size data representations (features/embeddings) from scientific data using pretrained foundational models. "
			"Currently supported input modalities are:\n"
			"* images\n"
			"* time series\n"
		)
		
		self.tool_categories = [
			"image",
			"timeseries",
		]
		
		self.input_requirements = {
			"supported_formats": [
				"fits",
				"png",
				"jpg", "jpeg",
				"csv", "ecsv",
				"npy", "npz",
				"json",
			],
			"expected_data": (
				"Astronomical/scientific image; time-series table/array; "
				"or JSON datalist containing image/time-series inputs or "
				"inline time-series records"
			),
			"notes": [
				"Image and time-series models use different runtime containers.",
				"Chronos-2 supports uni- and multivariate time series.",
				"Time-series inputs may use long, wide, or inline JSON representations.",
			]
		}
		
		self.limitations = [
			"Available preprocessing options depend on the selected model modality.",
			"Chronos-2 requires regularly sampled time series unless regularization is enabled.",
		]
		
		# - Define dictionary with allowed options
		self.valid_options= {
		
			
			# == MODEL OPTIONS ==
			'model' : EnumValueOption(
				name='model',
				value='',
				value_type=str,
				description='Feature extraction model to be used',
				category='MODEL',
				default_value='simclr_radio',
				allowed_values=[
					'simclr_radio',
					'dinov2',
					'dinov3',
					'dinov2_legacy',
					'siglip',
					'siglip2',
					'chronos2',
				]
			),

			# == INPUT OPTIONS ==
			'datalist-key' : ValueOption(
				name='datalist-key',
				value='',
				value_type=str,
				description='Dictionary key containing datalist entries',
				category='INPUT',
				default_value='data'
			),

			'nmax' : ValueOption(
				name='nmax',
				value='',
				value_type=int,
				description='Maximum number of datalist entries to process',
				category='INPUT',
				default_value='',
				min_value=1
			),
		
			# == PRE-PROCESSING OPTIONS ==
			"preproc-profile": EnumValueOption(
				name="preproc-profile",
				value="",
				value_type=str,
				description=(
					"Domain preprocessing profile. "
					"'simclr_radio' applies to image models; "
					"'default' is available for both image and time-series models."
				),
				category="PREPROCESSING",
				#default_value="",
				default_value="default",
				allowed_values=["default", "simclr_radio"]
			),
			'norm-min' : ValueOption(
				name='norm-min',
				value='',
				value_type=float, 
				description='Normalization min value (default=0)',
				category='PREPROCESSING',
				default_value=0.0,
				min_value=-1.0,
				max_value=0.0
			),
			'norm-max' : ValueOption(
				name='norm-max',
				value='',
				value_type=float, 
				description='Normalization max value (default=1)',
				category='PREPROCESSING',
				default_value=1.0,
				min_value=1.0,
				max_value=255.0
			),
			'imgsize' : ValueOption(
				name='imgsize',
				value='',
				value_type=int,
				description=(
					'Model input image size in pixels. '
					'If omitted, the selected model default is used.'
				),
				category='PREPROCESSING',
				default_value='',
				min_value=16,
				max_value=1024
			),
			'nchannels' : ValueOption(
				name='nchannels',
				value='',
				value_type=int,
				description=(
					'Number of model input channels. '
					'If omitted, the selected model default is used.'
				),
				category='PREPROCESSING',
				default_value='',
				min_value=1,
				max_value=1000
			),
			'clipdata' : Option(
				name='clipdata', 
				description='Clip image pixel value in range [mean-5*stddev, mean+30*stddev]', 
				category='PREPROCESSING',
				default_value=False
			),
			'zscale' : Option(
				name='zscale',
				description=(
					'Enable or disable z-scale stretching. '
					'If omitted, the preprocessing profile default is used.'
				),
				category='PREPROCESSING',
				default_value=None
			),
			'zscale-contrast' : ValueOption(
				name='zscale-contrast',
				value='',
				value_type=float, 
				description='zscale contrast value applied to all channels',
				category='PREPROCESSING',
				default_value=0.25,
				min_value=0.0,
				max_value=1.0,
			),
			'set-zero-to-min' : Option(
				name='set-zero-to-min',
				description=(
					'Replace zero/blank/non-finite pixels with the minimum '
					'valid non-zero image value.'
				),
				category='PREPROCESSING',
				default_value=False
			),
			'reset-meanstd' : Option(
				name='reset-meanstd',
				description='Reset SigLIP/SigLIP2 processor mean/std to 0/1',
				category='PREPROCESSING',
				default_value=False
			),
			'reset-rescale' : Option(
				name='reset-rescale',
				description='Disable SigLIP/SigLIP2 processor input rescaling',
				category='PREPROCESSING',
				default_value=False
			),
			
			# == TIME-SERIES PREPROCESSING OPTIONS ==
			'timeseries-layout' : EnumValueOption(
				name='timeseries-layout',
				value='',
				value_type=str,
				description='Time-series tabular layout',
				category='TIMESERIES',
				default_value='',
				allowed_values=['long', 'wide']
			),
			
			'time-column' : ValueOption(
				name='time-column',
				value='',
				value_type=str,
				description='Timestamp column for long-format time-series input',
				category='TIMESERIES',
				default_value=''
			),

			'value-columns' : ValueOption(
				name='value-columns',
				value='',
				value_type=str,
				description=(
					'Comma-separated time-series value columns. '
					'The container wrapper converts them to CLI arguments.'
				),
				category='TIMESERIES',
				default_value=''
			),

			'error-columns' : ValueOption(
				name='error-columns',
				value='',
				value_type=str,
				description='Comma-separated uncertainty/error columns',
				category='TIMESERIES',
				default_value=''
			),

			'value-prefixes' : ValueOption(
				name='value-prefixes',
				value='',
				value_type=str,
				description='Comma-separated value prefixes for wide-layout input',
				category='TIMESERIES',
				default_value=''
			),

			'channel-names' : ValueOption(
				name='channel-names',
				value='',
				value_type=str,
				description='Comma-separated names assigned to time-series channels',
				category='TIMESERIES',
				default_value=''
			),

			'label-column' : ValueOption(
				name='label-column',
				value='',
				value_type=str,
				description='Optional sample-level label column',
				category='TIMESERIES',
				default_value=''
			),

			'metadata-columns' : ValueOption(
				name='metadata-columns',
				value='',
				value_type=str,
				description='Comma-separated additional sample-level metadata columns',
				category='TIMESERIES',
				default_value=''
			),

			'time-start-key' : ValueOption(
				name='time-start-key',
				value='',
				value_type=str,
				description='Inline JSON field containing the initial timestamp',
				category='TIMESERIES',
				default_value=''
			),

			'cadence-key' : ValueOption(
				name='cadence-key',
				value='',
				value_type=str,
				description='Inline JSON field containing the sampling cadence',
				category='TIMESERIES',
				default_value=''
			),

			'regularize' : Option(
				name='regularize',
				description=(
					'Enable or disable regularization onto a fixed time grid. '
					'If omitted, the preprocessing profile default is used.'
				),
				category='TIMESERIES',
				default_value=None
			),

			'cadence' : ValueOption(
				name='cadence',
				value='',
				value_type=float,
				description='Regularization cadence in timestamp units',
				category='TIMESERIES',
				default_value='',
				min_value=0.0
			),

			'missing-strategy' : EnumValueOption(
				name='missing-strategy',
				value='',
				value_type=str,
				description='Missing-value strategy after regularization',
				category='TIMESERIES',
				default_value='',
				allowed_values=[
					'nan',
					'linear',
				]
			),
			
			# == TIME SERIES REPRESENTATION OPTIONS ==
			'aggregation' : EnumValueOption(
				name='aggregation',
				value='',
				value_type=str,
				description='Token aggregation used to produce a fixed-size representation',
				category='REPRESENTATION',
				default_value='',
				allowed_values=[
					'mean',
					'std',
					'max',
					'mean_std',
					'mean_max',
					'mean_std_max',
					'last',
					'reg',
					'flatten',
				]
			),

			'context-length' : ValueOption(
				name='context-length',
				value='',
				value_type=int,
				description='Optional maximum model context length',
				category='REPRESENTATION',
				default_value='',
				min_value=1
			),

			'batch-size' : ValueOption(
				name='batch-size',
				value='',
				value_type=int,
				description='Embedding batch size',
				category='REPRESENTATION',
				default_value='',
				min_value=1
			),
			
			# == SAVE OPTIONS ==
			'outfile' : ValueOption(
				name='outfile',
				value='',
				value_type=str, 
				description='Output filename (.json) containing embedding/feature data extracted',
				category='SAVE',
				default_value='fextractor_results.json'
			),
			
			# == RUN OPTIONS ==
			'device' : ValueOption(
				name='device',
				value='',
				value_type=str,
				description='Inference device, for example cuda, cuda:0, or cpu',
				category='RUN',
				default_value='cuda'
			),

			'skip-errors' : Option(
				name='skip-errors',
				description='Skip failed datalist entries instead of aborting the job',
				category='RUN',
				default_value=False
			),

			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
		
		} ## close options
		
		
		# - Define dictionary with job outputs produced
		self.job_outputs= {
		
		}
		
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
		
		
	def validate(self, job_options, data_inputs):
		"""Validate fextractor inputs and resolve the runtime container."""

		# - Validate options
		requested_options = set(
			job_options.keys()
		)
		
		valid = AppConfigurator.validate(
			self,
			job_options,
			data_inputs,
		)

		if not valid:
			return False

		# - Convert CAESAR boolean zscale=False to the negative
		#   command-line option expected by run_fextractor.sh.
		if "zscale" in self.job_options:
			zscale = self.job_options["zscale"]

			if zscale is False:
				self.cmd_args.append("--no-zscale")
				
				
		# - Convert CAESAR boolean regularize=False to the negative
		#   command-line option expected by the Chronos wrapper.
		if "regularize" in self.job_options:
			regularize = self.job_options["regularize"]

			if regularize is False:
				self.cmd_args.append("--no-regularize")		

		# - Resolve container variant
		model = self.job_options.get(
			"model",
			"simclr_radio",
		)
		
		image_models = {
			"simclr_radio",
			"dinov2",
			"dinov3",
			"dinov2_legacy",
			"siglip",
			"siglip2",
		}

		timeseries_models = {
			"chronos2",
		}

		image_only_options = {
			"norm-min",
			"norm-max",
			"imgsize",
			"nchannels",
			"clipdata",
			"zscale",
			"zscale-contrast",
			"set-zero-to-min",
			"reset-meanstd",
			"reset-rescale",
		}

		timeseries_only_options = {
			"timeseries-layout",
			"time-column",
			"value-columns",
			"error-columns",
			"value-prefixes",
			"channel-names",
			"label-column",
			"metadata-columns",
			"time-start-key",
			"cadence-key",
			"regularize",
			"cadence",
			"missing-strategy",
			"aggregation",
			"context-length",
			"batch-size",
		}

		if model in timeseries_models:
			invalid_options = (
				requested_options
				& image_only_options
			)

			if invalid_options:
				self.validation_status = (
					"Image-only option(s) not supported by model '%s': %s"
					% (
						model,
						", ".join(
							sorted(invalid_options)
						),
					)
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False

		if model in image_models:
			invalid_options = (
				requested_options
				& timeseries_only_options
			)

			if invalid_options:
				self.validation_status = (
					"Time-series-only option(s) not supported by model '%s': %s"
					% (
						model,
						", ".join(
							sorted(invalid_options)
						),
					)
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False

	
		if (
			model == "chronos2"
			and self.job_options.get(
				"preproc-profile",
				"default",
			) != "default"
		):
			self.validation_status = (
				"Chronos-2 currently supports only the 'default' "
				"time-series preprocessing profile"
			)

			logger.warning(
				self.validation_status,
				action="submitjob",
			)

			return False


		if model not in MODEL_CONTAINER_VARIANTS:
			self.validation_status = (
				"Cannot determine container variant for model '%s'" % model
			)
			logger.warning(
				self.validation_status,
				action="submitjob",
			)
			return False

		self.run_options["container_variant"] = (
			MODEL_CONTAINER_VARIANTS[model]
		)

		return True	
		
