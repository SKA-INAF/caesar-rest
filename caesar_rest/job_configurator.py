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
from flask import current_app

# Get logger
logger = logging.getLogger(__name__)




##############################
#   JOB CONFIGURATOR
##############################
class JobConfigurator(object):
	""" Class to configure job command """

	def __init__(self):
		""" Return a job configurator class """

		self.app_configurators= {
			'sfinder': SFinderConfigurator
		}

		
	def validate(self,app_name,job_inputs):
		""" Validate job inputs """

		# - Validate if job inputs are valid for app
		#   Delegate validation to app configurator
		if app_name not in self.app_configurators:
			msg= 'App ' + app_name + ' not known or supported'
			logger.warn(msg)
			return (None,None,msg)

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()

		#status= self.app_configurators[app_name].validate(job_inputs)
		status= configurator.validate(job_inputs)
		if status<0:
			status_msg= configurator.validation_status
			logger.warn("Given inputs for app %s failed to be validated!" % app_name)
			return (None,None,status_msg)

		# - Set app cmd & cmd args
		cmd= configurator.cmd
		cmd_args= configurator.cmd_args
		status_msg= configurator.validation_status
		
		return (cmd,cmd_args,status_msg)

	def get_app_description(self,app_name):
		""" Return a json dict describing given app """
		
		# - Check app name if found
		if app_name not in self.app_configurators:
			msg= 'App ' + app_name + ' not known or supported'
			logger.warn(msg)
			return None

		# - Create an instance of app configurator
		configurator= self.app_configurators[app_name]()

		# - Get description
		#d= configurator.describe_json()
		d= configurator.describe_dict()	

		return d

	def get_app_names(self):
		""" Return app names """
		
		d= {}
		app_names= []
		for app_name in self.app_configurators:
			app_names.append(app_name)
		d.update({'apps':app_names})

		#return json.loads(json.dumps(d))
		return d

##############################
#   APP CONFIGURATOR
##############################
class Option(object):

	def __init__(self,name,mandatory=False):
		self.name= name
		self.mandatory= mandatory
		self.value_required= False
		#self.value= ''
		#self.value_type= bool
		self.value= None
		self.value_type= type(None)

	def to_argopt(self):
		""" Convert option to cmdline format """
		
		if self.value_required:
			argopt= '--' + self.name + '=' + str(self.value)
		else:
			argopt= '--' + self.name

		return argopt

	def to_dict(self):
		""" Convert option to dictionary """
		
		if self.value_required:
			d= {self.name: {"mandatory":self.mandatory,"type":self.value_type.__name__}}
		else:
			d= {self.name: {"mandatory":self.mandatory,"type":"none"}}			
			
		return d
	

class ValueOption(Option):

	def __init__(self,name,value,value_type,mandatory=False):
		""" Return value option """
		Option.__init__(self,name,mandatory)
		self.value= value
		self.value_required= True
		self.value_type= value_type


class AppConfigurator(object):
	""" Class to define base app configurator """
  
	def __init__(self):
		""" Constructor"""

		self.job_inputs= ''
		self.cmd= ''
		self.cmd_args= []
		self.validation_status= ''
		self.valid_options= {}
		self.options= []

	def describe_dict(self):
		""" Return a dictionary describing valid options """
			
		d= {}
		for opt_name, option in self.valid_options.items():
			option_dict= option.to_dict()
			d.update(option_dict)

		return d

	def describe_str(self):
		""" Return a json string describing valid options """
			
		d= self.describe()
		return json.dumps(d)

	def describe_json(self):
		""" Return a json dictionary describing valid options """
			
		json_str= self.describe_str()
		return json.loads(json_str)


	def validate(self,job_inputs):
		""" Validate job input """

		logger.info("Validating given inputs ...")

		# - Check if job inputs are empty
		if not job_inputs:		
			self.validation_status= 'Empty job inputs given!'
			logger.warn(self.validation_status)
			return False

		# - Convert json string to dictionary
		print("type(job_inputs)")
		print(type(job_inputs))
		print(job_inputs)

		if not isinstance(job_inputs,dict):
			self.validation_status= 'Given job inputs data is not a dictionary!'
			logger.warn(self.validation_status)
			return False

		try:
			self.job_inputs= yaml.safe_load(json.dumps(job_inputs))

		except ValueError:
			self.validation_status= 'Failed to parse job inputs as json dictionary!'
			logger.warn(self.validation_status)
			return False

		print("type(self.job_inputs)")
		print(type(self.job_inputs))
		print(self.job_inputs)

		# - Validate options 
		valid= self.validate_options()
		print("--> %s args" % self.cmd)
		print(self.cmd_args)
		
		return valid


	def validate_options(self):
		""" Validate parsed options against valid expected options (provided in derived class) """

		# - Validate options
		for opt_name, option in self.valid_options.items():
			option_given= opt_name in self.job_inputs

			# - Check if mandatory option is given
			mandatory= option.mandatory
			if mandatory and not option_given:
				self.validation_status= ''.join(["Mandatory option ",opt_name," not present!"])
				logger.warn(self.validation_status)
				return False
	
			# - Skip if not given
			if not option_given:
				continue

			# - Check if required value
			value_required= option.value_required
			if value_required:
				# - Check for value type
				expected_val_type= option.value_type
				parsed_value= self.job_inputs[opt_name]
				parsed_value_type= type(parsed_value)
				if not isinstance(parsed_value,expected_val_type):
					self.validation_status= ''.join(["Option ",opt_name," expects a ",str(expected_val_type)," value type and not a ",str(parsed_value_type)," !"])
					logger.warn(self.validation_status)
					return False

				# - Add option
				value_option= ValueOption(opt_name,str(parsed_value),expected_val_type,mandatory)
				self.options.append(value_option)

				# - Convert to cmd arg format
				argopt= value_option.to_argopt()
				self.cmd_args.append(argopt)
			
			else: # No value required
				bool_option= Option(opt_name,mandatory)
				self.options.append(bool_option)

				# - Convert to cmd arg format
				argopt= bool_option.to_argopt()
				self.cmd_args.append(argopt)

		return True


##############################
#   SFINDER APP CONFIGURATOR
##############################

class SFinderConfigurator(AppConfigurator):
	""" Class to configure sfinder application """

	def __init__(self):
		""" Return sfinder configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'SFinderSubmitter.sh'
		self.cmd_args= []

		# - Define dictionary with allowed options
		self.valid_options= {
			# == INPUT OPTIONS ==
			'inputfile' : ValueOption('inputfile','',str,True),
			#'filelist' : ValueOption('filelist','',True),
		
			# == OUTPUT OPTIONS ==		
			'save-inputmap' : Option('save-inputmap'),
			'save-bkgmap' : Option('save-bkgmap'),
			'save-rmsmap' : Option('save-rmsmap'),
			'save-significancemap' : Option('save-significancemap'),
			'save-residualmap' : Option('save-residualmap'),
			'save-saliencymap' : Option('save-saliencymap'),
			'save-segmentedmap' : Option('save-segmentedmap'),
			'save-regions' : Option('save-regions'),
			'convertregionstowcs' : Option('convertregionstowcs'),
			'regionwcs' : ValueOption('regionwcs','',int),

			# == IMG READ OPTIONS ==
			'tilesize' : ValueOption('tilesize','',int),
			'tilestep' : ValueOption('tilestep','',float),
			'xmin' : ValueOption('xmin','',int),
			'xmax' : ValueOption('xmax','',int),
			'ymin' : ValueOption('ymin','',int),
			'ymax' : ValueOption('ymax','',int),

			# == STATS OPTIONS ==		
			'no-parallelmedian' : Option('no-parallelmedian'),

			# == BKG OPTIONS ==		
			'bmaj' : ValueOption('bmaj','',float),
			'bmin' : ValueOption('bmin','',float),
			'bpa' : ValueOption('bpa','',float),
			'mappixsize' : ValueOption('mappixsize','',float),
			'globalbkg' : Option('globalbkg'),
			'bkgestimator' : ValueOption('bkgestimator','',int),
			'bkgbox' : ValueOption('bkgbox','',int),
			'bkggrid' : ValueOption('bkggrid','',float),
			'no-bkg2ndpass' : Option('no-bkg2ndpass'),
			'bkgskipoutliers' : Option('bkgskipoutliers'),
			'sourcebkgboxborder' : ValueOption('sourcebkgboxborder','',int),

			# == SFINDER OPTIONS ==		
			'mergeedgesources' : Option('mergeedgesources'),
			'no-mergesources' : Option('no-mergesources'),
			'no-mergecompactsources' : Option('no-mergecompactsources'),
			'no-mergeextsources' : Option('no-mergeextsources'),

			# == COMPACT SOURCE SEARCH OPTIONS ==
			'no-compactsearch' : Option('no-compactsearch'),
			'npixmin' : ValueOption('npixmin','',int),
			'seedthr' : ValueOption('seedthr','',float),
			'mergethr' : ValueOption('mergethr','',float),
			'compactsearchiters' : ValueOption('compactsearchiters','',int),
			'seedthrstep' : ValueOption('seedthrstep','',float),
	
			# == COMPACT SOURCE SELECTION OPTIONS ==
			'selectsources' : Option('selectsources'),
			'no-boundingboxcut' : Option('no-boundingboxcut'),
			'minboundingbox' : ValueOption('minboundingbox','',int),
			'no-circratiocut' : Option('no-circratiocut'),
			'circratiothr' : ValueOption('circratiothr','',float),
			'no-elongationcut' : Option('no-elongationcut'),
			'elongationthr' : ValueOption('elongationthr','',float),
			'ellipsearearatiocut' : Option('ellipsearearatiocut'),
			'ellipsearearatiominthr' : ValueOption('ellipsearearatiominthr','',float),
			'ellipsearearatiomaxthr' : ValueOption('ellipsearearatiomaxthr','',float),
			'maxnpixcut' : Option('maxnpixcut'),
			'maxnpix' : ValueOption('maxnpix','',int),
			'no-nbeamscut' : Option('no-nbeamscut'),
			'nbeamsthr' : ValueOption('nbeamsthr','',float),

			# == COMPACT NESTED SOURCE OPTIONS ==
			'no-nestedsearch' : Option('no-nestedsearch'),
			'blobmaskmethod' : ValueOption('blobmaskmethod','',int),
			'nested-sourcetobeamthr' : ValueOption('nested-sourcetobeamthr','',float),
			'nested-blobthr' : ValueOption('nested-blobthr','',float),
			'nested-minmotherdist' : ValueOption('nested-minmotherdist','',int),
			'nested-maxmotherpixmatch' : ValueOption('nested-maxmotherpixmatch','',float),
			'nested-blobpeakzthr' : ValueOption('nested-blobpeakzthr','',float),
			'nested-blobpeakzthrmerge' : ValueOption('nested-blobpeakzthrmerge','',float),
			'nested-blobminscale' : ValueOption('nested-blobminscale','',float),
			'nested-blobmaxscale' : ValueOption('nested-blobmaxscale','',float),
			'nested-blobscalestep' : ValueOption('nested-blobscalestep','',float),
			'nested-blobkernfactor' : ValueOption('nested-blobkernfactor','',float),

			# == EXTENDED SOURCE SEARCH OPTIONS ==
			'no-extendedsearch' : Option('no-extendedsearch'),
			'extsfinder' : ValueOption('extsfinder','',int),
			'activecontour' : ValueOption('activecontour','',int),
			
			# == SOURCE RESIDUAL OPTIONS ==
			'computeresiduals' : Option('computeresiduals'),
			'res-removenested' : Option('res-removenested'),
			'res-zthr' : ValueOption('res-zthr','',float),
			'res-zhighthr' : ValueOption('res-zhighthr','',float),
			'dilatekernsize' : ValueOption('dilatekernsize','',int),
			'res-removedsourcetype' : ValueOption('res-removedsourcetype','',int),
			'res-pssubtractionmethod' : ValueOption('res-pssubtractionmethod','',int),

			# == SOURCE FITTING OPTIONS ==
			'fitsources' : Option('fitsources'),
			'fit-usethreads' : Option('fit-usethreads'),
			'fit-minimizer' : ValueOption('fit-minimizer','',str),
			'fit-minimizeralgo' : ValueOption('fit-minimizeralgo','',str),
			'fit-printlevel' : ValueOption('fit-printlevel','',int),
			'fit-strategy' : ValueOption('fit-strategy','',int),
			'fit-maxnbeams' : ValueOption('fit-maxnbeams','',int),
			'fit-maxcomponents' : ValueOption('fit-maxcomponents','',int),
			'fit-usenestedascomponents' : Option('fit-usenestedascomponents'),
			'fit-freebkg' : Option('fit-freebkg'),
			'fit-estimatedbkg' : Option('fit-estimatedbkg'),
			'fit-usebkgboxestimate' : Option('fit-usebkgboxestimate'),
			'fit-bkg' : ValueOption('fit-bkg','',float),
			'fit-ampllimit' : ValueOption('fit-ampllimit','',float),
			'prefit-freeampl' : Option('prefit-freeampl'),
			'fit-sigmalimit' : ValueOption('fit-sigmalimit','',float),
			'fit-thetalimit' : ValueOption('fit-thetalimit','',float),
			'fit-nobkglimits' : Option('fit-nobkglimits'),
			'fit-noampllimits' : Option('fit-noampllimits'),
			'fit-nosigmalimits' : Option('fit-nosigmalimits'),
			'fit-noposlimits' : Option('fit-noposlimits'),
			'fit-poslimit' : ValueOption('fit-poslimit','',int),
			'prefit-freepos' : Option('prefit-freepos'),
			'fit-nothetalimits' : Option('fit-nothetalimits'),
			'fit-fixsigma' : Option('fit-fixsigma'),
			'prefit-fixsigma' : Option('prefit-fixsigma'),
			'fit-fixtheta' : Option('fit-fixtheta'),
			'prefit-fixtheta' : Option('prefit-fixtheta'),
			'fit-peakminkern' : ValueOption('fit-peakminkern','',int),
			'fit-peakmaxkern' : ValueOption('fit-peakmaxkern','',int),
			'fit-peakmultiplicitythr' : ValueOption('fit-peakmultiplicitythr','',int),
			'fit-peakshifttol' : ValueOption('fit-peakshifttol','',int),
			'fit-peakzthrmin' : ValueOption('fit-peakzthrmin','',float),
			'fit-fcntol' : ValueOption('fit-fcntol','',float),
			'fit-maxniters' : ValueOption('fit-maxniters','',int),
			'fit-noimproveconvergence' : Option('fit-noimproveconvergence'),
			'fit-noretry' : Option('fit-noretry'),
			'fit-nretries' : ValueOption('fit-nretries','',int),
			'fit-parboundincreasestep' : ValueOption('fit-parboundincreasestep','',float),
			'fit-improveerrors' : Option('fit-improveerrors'),
			'fit-scaledatatomax' : Option('fit-scaledatatomax'),
			'fit-nochi2cut' : Option('fit-nochi2cut'),
			'fit-chi2cut' : ValueOption('fit-chi2cut','',float),
			'fit-useellipsecuts' : Option('fit-useellipsecuts'),
			
			# == SMOOTHING FILTER OPTIONS ==
			'no-presmoothing' : Option('no-presmoothing'),
			'smoothfilter' : ValueOption('smoothfilter','',int),
			'guidedfilter-radius' : ValueOption('guidedfilter-radius','',float),
			'guidedfilter-eps' : ValueOption('guidedfilter-eps','',float),

			# == SALIENCY FILTER OPTIONS ==
			'sp-size' : ValueOption('sp-size','',int),
			'sp-beta' : ValueOption('sp-beta','',float),
			'sp-minarea' : ValueOption('sp-minarea','',int),
			'saliency-nooptimalthr' : Option('saliency-nooptimalthr'),
			'saliency-thr' : ValueOption('saliency-thr','',float),
			'saliency-minreso' : ValueOption('saliency-minreso','',int),
			'saliency-maxreso' : ValueOption('saliency-maxreso','',int),
			'saliency-resostep' : ValueOption('saliency-resostep','',int),
			'saliency-nn' : ValueOption('saliency-nn','',float),
			'saliency-usebkgmap' : Option('saliency-usebkgmap'),
			'saliency-usermsmap' : Option('saliency-usermsmap'),
			'saliency-userobustpars' : Option('saliency-userobustpars'),

			# == ACTIVE-CONTOUR MAIN OPTIONS ==
			'ac-niters' : ValueOption('ac-niters','',int),
			'ac-levelset' : ValueOption('ac-levelset','',int),
			'ac-levelsetsize' : ValueOption('ac-levelsetsize','',float),
			'ac-tolerance' : ValueOption('ac-tolerance','',float),

			# == CHAN-VESE OPTIONS ==
			'cv-nitersinner' : ValueOption('cv-nitersinner','',int),
			'cv-nitersreinit' : ValueOption('cv-nitersreinit','',int),
			'cv-timestep' : ValueOption('cv-timestep','',float),
			'cv-wsize' : ValueOption('cv-wsize','',float),
			'cv-lambda1' : ValueOption('cv-lambda1','',float),
			'cv-lambda2' : ValueOption('cv-lambda2','',float),
			'cv-mu' : ValueOption('cv-mu','',float),
			'cv-nu' : ValueOption('cv-nu','',float),
			'cv-p' : ValueOption('cv-p','',float),

			# == WAVELET TRANSFORM FILTER OPTIONS ==
			'wtscalemin' : ValueOption('wtscalemin','',int),
			'wtscalemax' : ValueOption('wtscalemax','',int),

			# == RUN OPTIONS ==
			'run' : Option('run'),
			'envfile' : ValueOption('envfile','',str),
			'loglevel' : ValueOption('loglevel','',str),
			'maxfiles' : ValueOption('maxfiles','',int),
			'addrunindex' : Option('addrunindex'),
			'outdir' : ValueOption('outdir','',str),
			'no-logredir' : Option('no-logredir'),
			'no-mpi' : Option('no-mpi'),
			'mpioptions' : ValueOption('mpioptions','',str),
			'nproc' : ValueOption('nproc','',int),
			'nthreads' : ValueOption('nthreads','',int),
			'hostfile' : ValueOption('hostfile','',str),
			'containerrun' : Option('containerrun'),
			'containerimg' : ValueOption('containerimg','',str),
			'containeroptions' : ValueOption('containeroptions','',str),

			# == SFINDER SUBMISSION OPTIONS ==
			'submit' : Option('submit'),
			'batchsystem' : ValueOption('batchsystem','',str),
			'queue' : ValueOption('queue','',str),
			'jobwalltime' : ValueOption('jobwalltime','',str),
			'jobcpus' : ValueOption('jobcpus','',int),
			'jobnodes' : ValueOption('jobnodes','',int),
			'jobmemory' : ValueOption('jobmemory','',float),
			'jobusergroup' : ValueOption('jobusergroup','',str),

		} # close dict
	
			
	
	
