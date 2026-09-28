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
	"moirai2": "moirai",
	"fats": "fats",
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
			"Extract fixed-size data representations (features/embeddings) from scientific data using pretrained foundation models or statistical feature extractors. "
			"Currently supported input modalities are:\n"
			"* images\n"
			"* time series\n\n"
			"Time-series inputs can be supplied as CSV tables or JSON datalists. Both regularly and irregularly sampled time series are supported, depending on the selected backend. "
			"Time-series data may contain one or multiple value channels and optional measurement uncertainties."
		)
		
		
		self.tool_categories = [
			"image",
			"timeseries",
		]
		
		
		input_timeseries_long_format = (
			'Input long-format time-series CSV file has this format:\n'
			'- One observation/sample per row\n'
			'- time | float: Timestamp column, specified with the time-column option\n'
			'- var1,var2,... | float: One or more time-series value columns, specified with value-columns\n'
			'- var1_err,var2_err,... | float: Optional measurement uncertainty/error columns, specified with error-columns\n'
			'Regularly and irregularly sampled time series are supported. '
			'For irregular sampling, explicit timestamps must be provided.'
		)

		input_timeseries_wide_format = (
			'Input wide-format time-series CSV file has this format:\n'
			'- One time series per row/file\n'
			'- var1_0,var1_1,...,var1_N | float: Samples for the first value channel\n'
			'- var2_0,var2_1,...,var2_N | float: Samples for additional value channels\n'
			'- var1_err_0,var1_err_1,... | float: Optional uncertainty samples\n'
			'- time_0,time_1,...,time_N | float: Optional explicit timestamps for irregular sampling\n'
			'- t_start | float and dt | float: Optional initial timestamp and cadence for regular sampling\n'
			'Value column prefixes are specified with value-prefixes. '
			'Optional uncertainty prefixes are specified with error-prefixes. '
			'Irregular timestamp prefixes are specified with time-prefix. '
			'For regularly sampled wide data, time-start-column and cadence-column may be used.'
		)

		input_timeseries_json_file_format = (
			'Input JSON datalist with file-based time-series entries has this format:\n\n'
			'{\n'
			'  "data": [\n'
			'    {\n'
			'      "label": "X",\n'
			'      "filepath": "/path/to/timeseries.csv"\n'
			'    },\n'
			'    ...\n'
			'  ]\n'
			'}\n'
			'\n'
			'where:\n'
			'* filepath | str: Path to the input time-series CSV file\n'
			'* label | str or list(str): Optional class label(s)\n'
			'Additional metadata fields specified in each entry are preserved in the output JSON. '
			'The datalist dictionary key is configured with datalist-key (default=data).'
		)

		input_timeseries_json_irregular_format = (
			'Input JSON datalist with inline irregularly sampled time series has this format:\n\n'
			'{\n'
			'  "data": [\n'
			'    {\n'
			'      "t": [0.0, 0.7, 2.1, ...],\n'
			'      "var1": [1.0, 1.1, 0.9, ...],\n'
			'      "var2": [4.0, 4.5, 5.0, ...],\n'
			'      "var1_err": [0.1, 0.1, 0.2, ...],\n'
			'      "var2_err": [0.3, 0.2, 0.3, ...]\n'
			'    },\n'
			'    ...\n'
			'  ]\n'
			'}\n'
			'\n'
			'where:\n'
			'* t | list(float): Explicit observation timestamps, selected with time-column\n'
			'* var1,var2,... | list(float): Time-series value arrays, selected with value-columns\n'
			'* var1_err,var2_err,... | list(float): Optional uncertainty arrays, selected with error-columns\n'
			'Additional metadata fields specified in each entry are preserved in the output JSON.'
		)

		input_timeseries_json_regular_format = (
			'Input JSON datalist with inline regularly sampled time series has this format:\n\n'
			'{\n'
			'  "data": [\n'
			'    {\n'
			'      "t_start": 0.0,\n'
			'      "dt": 1.0,\n'
			'      "var1": [1.0, 1.1, 0.9, ...],\n'
			'      "var2": [4.0, 4.5, 5.0, ...],\n'
			'      "var1_err": [0.1, 0.1, 0.2, ...],\n'
			'      "var2_err": [0.3, 0.2, 0.3, ...]\n'
			'    },\n'
			'    ...\n'
			'  ]\n'
			'}\n'
			'\n'
			'where:\n'
			'* t_start | float: Initial timestamp, selected with time-start-key\n'
			'* dt | float: Sampling cadence, selected with cadence-key\n'
			'* var1,var2,... | list(float): Time-series value arrays, selected with value-columns\n'
			'* var1_err,var2_err,... | list(float): Optional uncertainty arrays, selected with error-columns\n'
			'Additional metadata fields specified in each entry are preserved in the output JSON.'
		)

		input_data_expected = (
			'Astronomical/scientific image or time-series input.\n\n'
			+ input_timeseries_long_format
			+ '\n\n'
			+ input_timeseries_wide_format
			+ '\n\n'
			+ input_timeseries_json_file_format
			+ '\n\n'
			+ input_timeseries_json_irregular_format
			+ '\n\n'
			+ input_timeseries_json_regular_format
		)

		self.input_requirements = {
			"supported_formats": [
				"fits",
				"png",
				"jpg",
				"jpeg",
				"csv",
				"ecsv",
				"npy",
				"npz",
				"json",
			],
			"expected_data": input_data_expected,
			"notes": [
				"Chronos-2 and Moirai-2 support uni- and multivariate time series.",
				"FATS processes each value channel independently and concatenates "
				"the resulting feature vectors; cross-channel relationships are "
				"not modeled.",
				"Measurement uncertainties are optional. FATS can use one "
				"uncertainty series per value channel.",
				"Available input and preprocessing options depend on the selected backend.",
			],
		}
		
		self.limitations = [
			"Available preprocessing options depend on the selected model modality.",

			"Chronos-2 requires regularly sampled time series unless "
			"regularization is enabled.",

			"FATS processes each time-series value channel independently; "
			"cross-variable relationships are not modeled.",

			"FATS does not support learned-representation aggregation, "
			"context-length, batch-size, regularization, or "
			"Moirai-specific patching options.",
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
					'moirai2',
					'fats',
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
				description=(
					'Timestamp column for long-format CSV input, or field '
					'name containing the timestamp array for inline JSON input'
				),
				category='TIMESERIES',
				default_value=''
			),

			'value-columns' : ValueOption(
				name='value-columns',
				value='',
				value_type=str,
				description=(
					'Colon-separated time-series value columns. '
					'The container wrapper converts them to CLI arguments.'
				),
				category='TIMESERIES',
				default_value=''
			),

			'error-columns' : ValueOption(
				name='error-columns',
				value='',
				value_type=str,
				description=(
					'Colon-separated measurement uncertainty/error columns '
					'or inline JSON uncertainty-array fields. '
					'For FATS, one error field must be supplied per value field.'
				),
				category='TIMESERIES',
				default_value=''
			),

			'value-prefixes' : ValueOption(
				name='value-prefixes',
				value='',
				value_type=str,
				description='Colon-separated value prefixes for wide-layout input',
				category='TIMESERIES',
				default_value=''
			),

			'error-prefixes' : ValueOption(
				name='error-prefixes',
				value='',
				value_type=str,
				description=(
					'Colon-separated uncertainty/error prefixes for '
					'wide-layout time-series input. One error prefix '
					'must be supplied per value prefix.'
				),
				category='TIMESERIES',
				default_value=''
			),

			'time-prefix' : ValueOption(
				name='time-prefix',
				value='',
				value_type=str,
				description=(
					'Prefix of indexed timestamp columns for irregularly '
					'sampled wide-layout time-series input'
				),
				category='TIMESERIES',
				default_value=''
			),

			'time-start-column' : ValueOption(
				name='time-start-column',
				value='',
				value_type=str,
				description=(
					'Column containing the initial timestamp for regularly '
					'sampled wide-layout time-series input'
				),
				category='TIMESERIES',
				default_value=''
			),

			'cadence-column' : ValueOption(
				name='cadence-column',
				value='',
				value_type=str,
				description=(
					'Column containing the sampling cadence for regularly '
					'sampled wide-layout time-series input'
				),
				category='TIMESERIES',
				default_value=''
			),

			'channel-names' : ValueOption(
				name='channel-names',
				value='',
				value_type=str,
				description=(
					'Colon-separated names assigned to time-series channels. '
					'For FATS these names prefix the per-channel feature names.'
				),
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
				description='Colon-separated additional sample-level metadata columns',
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
			
			'patching-mode' : EnumValueOption(
				name='patching-mode',
				value='',
				value_type=str,
				description=(
					'Moirai-2 patching mode. '
					'If omitted, the backend default is used.'
				),
				category='REPRESENTATION',
				default_value='',
				allowed_values=[
					'time_only',
					'time_variate',
				]
			),

			'token-order' : EnumValueOption(
				name='token-order',
				value='',
				value_type=str,
				description=(
					'Moirai-2 token ordering used with time_variate patching. '
					'If omitted, the backend default is used.'
				),
				category='REPRESENTATION',
				default_value='',
				allowed_values=[
					'by_variate',
					'interleave_time',
				]
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
			"moirai2",
			"fats",
		}

		# - Convert CAESAR boolean regularize=False to the negative
		#   command-line option expected by time-series wrappers.
		if (
			model in {
				"chronos2",
				"moirai2",
			}
			and "regularize" in self.job_options
		):
			regularize = self.job_options[
				"regularize"
			]

			if regularize is False:
				self.cmd_args.append(
					"--no-regularize"
				)

		# - Convert CAESAR boolean zscale=False to the negative
		#   command-line option expected by run_fextractor.sh.
		if (
			model in image_models
			and "zscale" in self.job_options
		):
			zscale = self.job_options["zscale"]

			if zscale is False:
				self.cmd_args.append("--no-zscale")
				
				
		# - Define options only available for certain models
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
			"error-prefixes",
			"time-prefix",
			"time-start-column",
			"cadence-column",
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
			"patching-mode",
			"token-order",
		}
		
		chronos_only_options = {
			"context-length",
			"batch-size",
		}

		moirai_only_options = {
			"patching-mode",
			"token-order",
		}
		
		fats_unsupported_options = {
			"preproc-profile",
			"label-column",
			"metadata-columns",
			"regularize",
			"cadence",
			"missing-strategy",
			"aggregation",
			"context-length",
			"batch-size",
			"patching-mode",
			"token-order",
			"device",
			"skip-errors",
		}

		
		# ======================================
		# ==     CHECK TIME-SERIES OPTIONS
		# ======================================
		# - Check time series model is not given image-only options
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


		# - Check time-series preprocessing profile
		if (
			model in {
				"chronos2",
				"moirai2",
			}
			and self.job_options.get(
				"preproc-profile",
				"default",
			) != "default"
		):
			self.validation_status = (
				"Time-series model '%s' currently supports only the "
				"'default' preprocessing profile"
				% model
			)

			logger.warning(
				self.validation_status,
				action="submitjob",
			)

			return False


		# - Check chronos options
		if model == "chronos2":
			invalid_options = (
				requested_options
				& moirai_only_options
			)

			if invalid_options:
				self.validation_status = (
					"Moirai-2-only option(s) not supported by model '%s': %s"
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

		# - Check moirai options
		if model == "moirai2":
			invalid_options = (
				requested_options
				& chronos_only_options
			)

			if invalid_options:
				self.validation_status = (
					"Chronos-2-only option(s) not supported by model '%s': %s"
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

		
		# - Check FATS options
		if model == "fats":

			# - Check for invalid options
			invalid_options = (
				requested_options
				& fats_unsupported_options
			)

			if invalid_options:
				self.validation_status = (
					"Option(s) not supported by FATS: %s"
					% ", ".join(
						sorted(invalid_options)
					)
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False


			# - Validate input data
			if isinstance(
				data_inputs,
				list,
			):
				self.validation_status = (
					"FATS expects one input CSV file or one JSON "
					"datalist per job"
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False


			input_ext = os.path.splitext(
				str(data_inputs)
			)[1].lower()

			if input_ext not in {
				".csv",
				".json",
			}:
				self.validation_status = (
					"FATS supports CSV or JSON input, got '%s'"
					% input_ext
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False


			layout = self.job_options.get(
				"timeseries-layout",
				"long",
			)

			if not layout:
				layout = "long"


			######################################
			# - Validate JSON input
			######################################

			if input_ext == ".json":

				value_columns = self.job_options.get(
					"value-columns",
					"",
				)

				error_columns = self.job_options.get(
					"error-columns",
					"",
				)

				channel_names = self.job_options.get(
					"channel-names",
					"",
				)

				time_column = self.job_options.get(
					"time-column",
					"",
				)

				time_start_key = self.job_options.get(
					"time-start-key",
					"",
				)

				cadence_key = self.job_options.get(
					"cadence-key",
					"",
				)


				# - Regular inline JSON requires both time keys
				if bool(
					time_start_key
				) != bool(
					cadence_key
				):
					self.validation_status = (
						"FATS inline JSON requires both "
						"'time-start-key' and 'cadence-key'"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				# - Explicit irregular time and regular time definition
				#   are mutually exclusive.
				if (
					time_column
					and (
						time_start_key
						or cadence_key
					)
				):
					self.validation_status = (
						"FATS inline JSON must use either "
						"'time-column' or "
						"'time-start-key'+'cadence-key', not both"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				# - If value-columns is specified, validate its syntax.
				#   It is not mandatory here because a JSON datalist may
				#   contain file-backed entries instead of inline records.
				value_column_list = []

				if value_columns:
					value_column_list = [
						item.strip()
						for item in value_columns.split(":")
					]

					if any(
						not item
						for item in value_column_list
					):
						self.validation_status = (
							"FATS 'value-columns' contains "
							"an empty field name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(value_column_list))
						!= len(value_column_list)
					):
						self.validation_status = (
							"FATS 'value-columns' contains "
							"duplicate field names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


				# - Optional inline JSON error arrays.
				if error_columns:
					if not value_column_list:
						self.validation_status = (
							"FATS 'error-columns' requires "
							"'value-columns' for inline JSON input"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					error_column_list = [
						item.strip()
						for item in error_columns.split(":")
					]

					if any(
						not item
						for item in error_column_list
					):
						self.validation_status = (
							"FATS 'error-columns' contains "
							"an empty field name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(error_column_list))
						!= len(error_column_list)
					):
						self.validation_status = (
							"FATS 'error-columns' contains "
							"duplicate field names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(error_column_list)
						!= len(value_column_list)
					):
						self.validation_status = (
							"FATS requires one error field per value field "
							"(%d value fields, %d error fields)"
							% (
								len(value_column_list),
								len(error_column_list),
							)
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


				# - Optional logical channel names for inline records.
				if channel_names:
					channel_name_list = [
						item.strip()
						for item in channel_names.split(":")
					]

					if any(
						not item
						for item in channel_name_list
					):
						self.validation_status = (
							"FATS 'channel-names' contains "
							"an empty channel name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(channel_name_list))
						!= len(channel_name_list)
					):
						self.validation_status = (
							"FATS 'channel-names' contains "
							"duplicate names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


					# Inline JSON or long-layout file datalist
					if value_column_list:
						if (
							len(channel_name_list)
							!= len(value_column_list)
						):
							self.validation_status = (
								"FATS requires one channel name per value field "
								"(%d value fields, %d channel names)"
								% (
									len(value_column_list),
									len(channel_name_list),
								)
							)

							logger.warning(
								self.validation_status,
								action="submitjob",
							)

							return False


					# Wide-layout file datalist
					elif layout == "wide":
						value_prefixes = self.job_options.get(
							"value-prefixes",
							"",
						)

						if value_prefixes:
							value_prefix_list = [
								item.strip()
								for item in value_prefixes.split(":")
							]

							if (
								len(channel_name_list)
								!= len(value_prefix_list)
							):
								self.validation_status = (
									"FATS requires one channel name per "
									"value prefix (%d value prefixes, "
									"%d channel names)"
									% (
										len(value_prefix_list),
										len(channel_name_list),
									)
								)

								logger.warning(
									self.validation_status,
									action="submitjob",
								)

								return False


			######################################
			# - Validate CSV long layout
			######################################

			elif layout == "long":

				value_columns = self.job_options.get(
					"value-columns",
					"",
				)

				if not value_columns:
					self.validation_status = (
						"FATS long-layout CSV input requires "
						"'value-columns'"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				value_column_list = [
					item.strip()
					for item in value_columns.split(":")
				]

				if any(
					not item
					for item in value_column_list
				):
					self.validation_status = (
						"FATS 'value-columns' contains "
						"an empty column name"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False

				if (
					len(set(value_column_list))
					!= len(value_column_list)
				):
					self.validation_status = (
						"FATS 'value-columns' contains "
						"duplicate column names"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				error_columns = self.job_options.get(
					"error-columns",
					"",
				)

				if error_columns:
					if not self.job_options.get(
						"time-column",
						"",
					):
						self.validation_status = (
							"FATS requires 'time-column' when "
							"'error-columns' are provided"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					error_column_list = [
						item.strip()
						for item in error_columns.split(":")
					]

					if any(
						not item
						for item in error_column_list
					):
						self.validation_status = (
							"FATS 'error-columns' contains "
							"an empty column name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(error_column_list))
						!= len(error_column_list)
					):
						self.validation_status = (
							"FATS 'error-columns' contains "
							"duplicate column names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(error_column_list)
						!= len(value_column_list)
					):
						self.validation_status = (
							"FATS requires one error column per value column "
							"(%d value columns, %d error columns)"
							% (
								len(value_column_list),
								len(error_column_list),
							)
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


				channel_names = self.job_options.get(
					"channel-names",
					"",
				)

				if channel_names:
					channel_name_list = [
						item.strip()
						for item in channel_names.split(":")
					]

					if any(
						not item
						for item in channel_name_list
					):
						self.validation_status = (
							"FATS 'channel-names' contains "
							"an empty channel name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(channel_name_list))
						!= len(channel_name_list)
					):
						self.validation_status = (
							"FATS 'channel-names' contains duplicate names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(channel_name_list)
						!= len(value_column_list)
					):
						self.validation_status = (
							"FATS requires one channel name per value column "
							"(%d value columns, %d channel names)"
							% (
								len(value_column_list),
								len(channel_name_list),
							)
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


			######################################
			# - Validate CSV wide layout
			######################################

			elif layout == "wide":

				value_prefixes = self.job_options.get(
					"value-prefixes",
					"",
				)

				if not value_prefixes:
					self.validation_status = (
						"FATS wide-layout CSV input requires "
						"'value-prefixes'"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				value_prefix_list = [
					item.strip()
					for item in value_prefixes.split(":")
				]

				if any(
					not item
					for item in value_prefix_list
				):
					self.validation_status = (
						"FATS 'value-prefixes' contains "
						"an empty prefix"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False

				if (
					len(set(value_prefix_list))
					!= len(value_prefix_list)
				):
					self.validation_status = (
						"FATS 'value-prefixes' contains "
						"duplicate prefixes"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				error_prefixes = self.job_options.get(
					"error-prefixes",
					"",
				)

				if error_prefixes:
					error_prefix_list = [
						item.strip()
						for item in error_prefixes.split(":")
					]

					if any(
						not item
						for item in error_prefix_list
					):
						self.validation_status = (
							"FATS 'error-prefixes' contains "
							"an empty prefix"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(error_prefix_list))
						!= len(error_prefix_list)
					):
						self.validation_status = (
							"FATS 'error-prefixes' contains "
							"duplicate prefixes"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(error_prefix_list)
						!= len(value_prefix_list)
					):
						self.validation_status = (
							"FATS requires one error prefix per value prefix "
							"(%d value prefixes, %d error prefixes)"
							% (
								len(value_prefix_list),
								len(error_prefix_list),
							)
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


				channel_names = self.job_options.get(
					"channel-names",
					"",
				)

				if channel_names:
					channel_name_list = [
						item.strip()
						for item in channel_names.split(":")
					]

					if any(
						not item
						for item in channel_name_list
					):
						self.validation_status = (
							"FATS 'channel-names' contains "
							"an empty channel name"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(set(channel_name_list))
						!= len(channel_name_list)
					):
						self.validation_status = (
							"FATS 'channel-names' contains duplicate names"
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False

					if (
						len(channel_name_list)
						!= len(value_prefix_list)
					):
						self.validation_status = (
							"FATS requires one channel name per value prefix "
							"(%d value prefixes, %d channel names)"
							% (
								len(value_prefix_list),
								len(channel_name_list),
							)
						)

						logger.warning(
							self.validation_status,
							action="submitjob",
						)

						return False


				time_prefix = self.job_options.get(
					"time-prefix",
					"",
				)

				time_start_column = self.job_options.get(
					"time-start-column",
					"",
				)

				cadence_column = self.job_options.get(
					"cadence-column",
					"",
				)


				if (
					time_prefix
					and (
						time_start_column
						or cadence_column
					)
				):
					self.validation_status = (
						"FATS wide-layout input must use either "
						"'time-prefix' or "
						"'time-start-column'+'cadence-column', "
						"not both"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


				if bool(
					time_start_column
				) != bool(
					cadence_column
				):
					self.validation_status = (
						"'time-start-column' and 'cadence-column' "
						"must be supplied together"
					)

					logger.warning(
						self.validation_status,
						action="submitjob",
					)

					return False


			else:
				self.validation_status = (
					"Unsupported FATS time-series layout '%s'"
					% layout
				)

				logger.warning(
					self.validation_status,
					action="submitjob",
				)

				return False
		
		
		# ======================================
		# ==     CHECK IMAGE OPTIONS
		# ======================================
		# - Check image model options
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

		# ======================================
		# ==     CHECK CONTAINER IMAGE OPTIONS
		# ======================================
		# - Check model container image variants
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
		
