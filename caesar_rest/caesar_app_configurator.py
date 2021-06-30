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

# Import caesare rest momdules
from caesar_rest import oidc
from caesar_rest import mongo
from caesar_rest import utils
from caesar_rest.base_app_configurator import AppConfigurator
from caesar_rest.base_app_configurator import Option, ValueOption, EnumValueOption

# Get logger
#logger = logging.getLogger(__name__)
from caesar_rest import logger


#######################################
#   CAESAR SFINDER APP CONFIGURATOR
#######################################

class CaesarAppConfigurator(AppConfigurator):
	""" Class to configure CAESAR sfinder application """

	def __init__(self):
		""" Return caesar sfinder app configurator class """
		AppConfigurator.__init__(self)

		# - Define cmd name
		self.cmd= 'SFinderSubmitter.sh'
		self.cmd_args= []
		self.batch_processing_support= True

		# - Define dictionary with allowed options
		self.valid_options= {
			# == INPUT OPTIONS ==
			#'inputfile' : ValueOption('inputfile','',str,True),
			#'filelist' : ValueOption('filelist','',True),
		
			# == OUTPUT OPTIONS ==
			'save-fits' : Option(
				name='save-fits', 
				description='Save maps (if save enabled) in FITS format (default=ROOT format)', 
				category='OUTPUT'
			),
			'save-inputmap' : Option(
				name='save-inputmap', 
				description='Save input map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-bkgmap' : Option(
				name='save-bkgmap', 
				description='Save bkg map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-rmsmap' : Option(
				name='save-rmsmap', 
				description='Save rms map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-significancemap' : Option(
				name='save-significancemap', 
				description='Save significance map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-residualmap' : Option(
				name='save-residualmap', 
				description='Save residual map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-saliencymap' : Option(
				name='save-saliencymap', 	
				description='Save saliency map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-segmentedmap' : Option(
				name='save-segmentedmap', 
				description='Save segmented map in output ROOT file (default=no)', 
				category='OUTPUT'
			),
			'save-regions' : Option(
				name='save-regions', 
				description='Save DS9 regions (default=no)', 
				category='OUTPUT'
			),
			'convertregionstowcs' : Option(
				name='convertregionstowcs', 
				description='Save DS9 regions in WCS format (default=no)', 
				category='OUTPUT', 
				advanced=True
			),
			#'regionwcs' : ValueOption(
			#	name='regionwcs',
			#	value='',
			#	value_type=int, 
			#	description='DS9 region WCS output format (0=J2000,1=B1950,2=GALACTIC) (default=0)', 
			#	category='OUTPUT', 
			#	advanced=True,
			#	default_value=0,
			#	min_value=0,
			#	max_value=2
			#),
			'regionwcs' : EnumValueOption(
				name='regionwcs',
				value='',
				value_type=str, 
				description='DS9 region WCS output format {J2000,B1950,GALACTIC} (default=J2000)', 
				category='OUTPUT', 
				advanced=True,
				default_value='J2000',
				allowed_values=['J2000', 'B1950', 'GALACTIC']
			),

			
			# == IMG READ OPTIONS ==
			'xmin' : ValueOption(
				name='xmin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel x=xmin (default=0=read full image)',
				category='IMGREAD',
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'xmax' : ValueOption(
				name='xmax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel x=xmax (default=0=read full image)',
				category='IMGREAD',	
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'ymin' : ValueOption(
				name='ymin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel y=xmin (default=0=read full image)',
				category='IMGREAD',	
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'ymax' : ValueOption(
				name='ymax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel y=ymax (default=0=read full image)',
				category='IMGREAD',
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),

			# == STATS OPTIONS ==		
			'no-parallelmedian' : Option(
				name='no-parallelmedian', 
				description='Switch off parallel median algorithm (based on parallel nth-element)',
				category='IMGSTATS',
				advanced=True
			),

			# == BKG OPTIONS ==		
			'bmaj' : ValueOption(
				name='bmaj',
				value='',
				value_type=float, 
				description='User-supplied beam Bmaj in arcsec (NB: used only when beam info is not available in input map) (default: 10 arcsec)',
				category='IMGBKG',
				advanced=True,
				default_value=10,
				min_value=0,
				max_value=3600
			),
			'bmin' : ValueOption(
				name='bmin',
				value='',
				value_type=float, 
				description='User-supplied beam Bmin in arcsec (NB: used only when beam info is not available in input map) (default: 5 arcsec)',
				category='IMGBKG',
				advanced=True,
				default_value=5,
				min_value=0,
				max_value=3600
			),
			'bpa' : ValueOption(
				name='bpa',
				value='',
				value_type=float, 
				description='User-supplied beam position angle in degrees (NB: used only when beam info is not available in input map) (default: 0 deg)',
				category='IMGBKG',
				advanced=True,
				default_value=0,
				min_value=0,
				max_value=180
			),
			'mappixsize' : ValueOption(
				name='mappixsize',
				value='',
				value_type=float, 
				description='Map pixel size in arcsec (NB: used only when info is not available in input map) (default=1 arcsec)',
				category='IMGBKG',
				advanced=True,
				default_value=1,
				min_value=0,
				max_value=3600
			),
			'globalbkg' : Option(
				name='globalbkg', 
				description='Use global bkg (default=use local bkg)',
				category='IMGBKG'	
			),
			#'bkgestimator' : ValueOption(
			#	name='bkgestimator',
			#	value='',
			#	value_type=int, 
			#	description='Stat estimator used for bkg (1=Mean,2=Median,3=BiWeight,4=ClippedMedian) (default=2)',
			#	category='IMGBKG',
			#	default_value=2,
			#	min_value=1,
			#	max_value=4
			#),
			'bkgestimator' : EnumValueOption(
				name='bkgestimator',
				value='',
				value_type=str, 
				description='Stat estimator used for bkg',
				category='IMGBKG',
				default_value="Median",
				allowed_values=["Mean", "Median", "BiWeight", "ClippedMedian"]
			),
			'bkgboxpix': Option(
				name='bkgboxpix', 
				description='Consider box size option expressed in pixels and not as a multiple of beam size (default=no)',
				category='IMGBKG'
			), 
			'bkgbox' : ValueOption(
				name='bkgbox',
				value='',
				value_type=float, 
				description='Box size (multiple of beam size) used to compute local bkg (default=20 x beam)',
				category='IMGBKG',
				default_value=20,
				min_value=0.01,
				max_value=1000.
			),
			'bkggrid' : ValueOption(
				name='bkggrid',
				value='',
				value_type=float, 
				description='Grid size (fraction of bkg box) used to compute local bkg (default=0.2 x box)',
				category='IMGBKG',
				default_value=0.2,
				min_value=0.,
				max_value=1.
			),
			'no-bkg2ndpass' : Option(
				name='no-bkg2ndpass', 
				description='Do not perform a 2nd pass in bkg estimation (default=true)',
				category='IMGBKG',
				advanced=True
			),
			'bkgskipoutliers' : Option(
				name='bkgskipoutliers', 
				description='Remove bkg outliers (blobs above seed thr) when estimating bkg (default=no)',
				category='IMGBKG',
				advanced=True
			),
			'sourcebkgboxborder' : ValueOption(
				name='sourcebkgboxborder',
				value='',
				value_type=int, 
				description='Border size (in pixels) of box around source bounding box used to estimate bkg for fitting (default=20)',
				category='IMGBKG',
				advanced=True,
				default_value=20,
				min_value=0,
				max_value=1000
			),

			# == COMPACT SOURCE SEARCH OPTIONS ==
			'no-compactsearch' : Option(
				name='no-compactsearch', 
				description='Do not search compact sources',
				category='COMPACT-SOURCES'
			),
			'npixmin' : ValueOption(
				name='npixmin',
				value='',
				value_type=int, 
				description='Minimum number of pixel to form a compact source (default=5 pixels)',
				category='COMPACT-SOURCES',
				default_value=5,
				min_value=0,
				max_value=10000
			),
			'seedthr' : ValueOption(
				name='seedthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used in flood-fill (default=5 sigmas)',
				category='COMPACT-SOURCES',
				default_value=5,
				min_value=0,
				max_value=10000
			),
			'mergethr' : ValueOption(
				name='mergethr',
				value='',
				value_type=float, 
				description='Merge threshold (in nsigmas) used in flood-fill (default=2.6 sigmas)',
				category='COMPACT-SOURCES',
				default_value=2.6,
				min_value=0,
				max_value=10000
			),
			'compactsearchiters' : ValueOption(
				name='compactsearchiters',
				value='',
				value_type=int, 
				description='Maximum number of compact source search iterations (default=1)',
				category='COMPACT-SOURCES',
				default_value=1,
				min_value=0,
				max_value=100
			),
			'seedthrstep' : ValueOption(
				name='seedthrstep',
				value='',
				value_type=float, 
				description='Seed thr decrease step across iterations (default=0.5)',
				category='COMPACT-SOURCES',
				default_value=0.5,
				min_value=0,
				max_value=10
			),
	
			# == COMPACT SOURCE SELECTION OPTIONS ==
			'selectsources' : Option(
				name='selectsources', 
				description='Apply selection to compact sources found (default=false)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION'
			),
			'no-boundingboxcut' : Option(
				name='no-boundingboxcut', 
				description='Do not apply bounding box cut (default=apply)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION'
			),
			'minboundingbox' : ValueOption(
				name='minboundingbox',
				value='',
				value_type=int, 
				description='Minimum bounding box cut in pixels (NB: source tagged as bad if below this threshold) (default=2)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=2,
				min_value=0,
				max_value=1000000
			),
			'no-circratiocut' : Option(
				name='no-circratiocut', 
				description='Do not apply circular ratio parameter cut (default=apply)',	
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True
			),
			'circratiothr' : ValueOption(
				name='circratiothr',
				value='',
				value_type=float, 
				description='Circular ratio threshold (0=line, 1=circle) (source passes point-like cut if above this threshold) (default=0.4)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',	
				advanced=True,
				default_value=0.4,
				min_value=0.,
				max_value=1.
			),
			'no-elongationcut' : Option(
				name='no-elongationcut', 
				description='Do not apply elongation parameter cut (default=apply)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True
			),
			'elongationthr' : ValueOption(
				name='elongationthr',
				value='',
				value_type=float, 
				description='Elongation threshold (source passes point-like cut if below this threshold (default=0.7)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=0.7,
				min_value=0.,
				max_value=1.
			),
			'ellipsearearatiocut' : Option(
				name='ellipsearearatiocut', 
				description='Apply ellipse area ratio parameter cut (default=not applied)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True
			),
			'ellipsearearatiominthr' : ValueOption(
				name='ellipsearearatiominthr',
				value='',
				value_type=float, 
				description='Ellipse area ratio min threshold (default=0.6)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=0.6,
				min_value=0.,
				max_value=10.
			),
			'ellipsearearatiomaxthr' : ValueOption(
				name='ellipsearearatiomaxthr',
				value='',
				value_type=float, 
				description='Ellipse area ratio max threshold (default=1.4)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=1.4,
				min_value=0.,
				max_value=10.
			),
			'maxnpixcut' : Option(
				name='maxnpixcut', 
				description='Apply max pixels cut (NB: source below this thr passes the point-like cut) (default=not applied)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION'
			),
			'maxnpix' : ValueOption(
				name='maxnpix',
				value='',
				value_type=int, 
				description='Max number of pixels for point-like sources (source passes point-like cut if below this threshold) (default=1000)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=1000,
				min_value=0.,
				max_value=10000000
			),
			'no-nbeamscut' : Option(
				name='no-nbeamscut', 
				description='Use number of beams in source cut (default=applied)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION'
			),
			'nbeamsthr' : ValueOption(
				name='nbeamsthr',
				value='',
				value_type=float, 
				description='nBeams threshold (sources passes point-like cut if nBeams<thr) (default=3)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=3,
				min_value=0.,
				max_value=1000.
			),


			# == COMPACT NESTED SOURCE OPTIONS ==
			'no-nestedsearch' : Option(
				name='no-nestedsearch', 
				description='Do not search nested sources (default=search)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES'
			),
			#'blobmaskmethod' : ValueOption(
			#	name='blobmaskmethod',
			#	value='',
			#	value_type=int, 
			#	description='Blob mask method (1=gaus smooth+Laplacian,2=multi-scale LoG) (default=2)',
			#	category='COMPACT-SOURCES',
			#	subcategory='NESTED-SOURCES',
			#	default_value=2,
			#	min_value=1,
			#	max_value=2
			#),
			'blobmaskmethod' : EnumValueOption(
				name='blobmaskmethod',
				value='',
				value_type=str, 
				description='Blob mask method',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value='MultiScaleLoG',
				allowed_values=['GausLaplacian', 'MultiScaleLoG']
			),

			'nested-sourcetobeamthr' : ValueOption(
				name='nested-sourcetobeamthr',
				value='',
				value_type=float, 
				description='Source area/beam thr to add nested sources (e.g. npix>thr*beamArea). NB: thr=0 means always if searchNestedSources is enabled (default=5)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=5.,
				min_value=0.,
				max_value=1000000.
			),
			'nested-blobthr' : ValueOption(
				name='nested-blobthr',
				value='',
				value_type=float, 
				description='Threshold (multiple of curvature median) used for nested blob finding (default=0)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				advanced=True,
				default_value=0.,
				min_value=0.,
				max_value=100.
			),
			'nested-minmotherdist' : ValueOption(
				name='nested-minmotherdist',
				value='',
				value_type=int, 
				description='Minimum distance in pixels (in x or y) between nested and parent blob below which nested is skipped (default=2)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				advanced=True,
				default_value=2,
				min_value=0,
				max_value=100
			),
			'nested-maxmotherpixmatch' : ValueOption(
				name='nested-maxmotherpixmatch',
				value='',
				value_type=float, 
				description='Maximum fraction of matching pixels between nested and parent blob above which nested is skipped (default=0.5)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				advanced=True,
				default_value=0.5,
				min_value=0.,
				max_value=1.
			),
			'nested-blobpeakzthr' : ValueOption(
				name='nested-blobpeakzthr',
				value='',
				value_type=float, 
				description='Nested blob peak significance threshold (in scale curv map) (default=5)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=5.,
				min_value=0.,
				max_value=10000.
			),
			'nested-blobpeakzthrmerge' : ValueOption(
				name='nested-blobpeakzthrmerge',
				value='',
				value_type=float, 
				description='Nested blob significance merge threshold (in scale curv map) (default=2.5)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=2.5,
				min_value=0.,
				max_value=10000.
			),
			'nested-blobminscale' : ValueOption(	
				name='nested-blobminscale',
				value='',
				value_type=float,
				description='Nested blob min scale search factor f (blob sigma_min=f x beam width) (default=1)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=1.,
				min_value=0.,
				max_value=10000.
			),
			'nested-blobmaxscale' : ValueOption(
				name='nested-blobmaxscale',
				value='',
				value_type=float,
				description='Nested blob max scale search factor f (blob sigma_max=f x beam width) (default=3)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=3.,
				min_value=0.,
				max_value=10000.
			),
			'nested-blobscalestep' : ValueOption(
				name='nested-blobscalestep',
				value='',
				value_type=float, 
				description='Nested blob scale step (sigma=sigma_min + step) (default=1)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=1.,
				min_value=0.,
				max_value=10000.
			),
			'nested-blobkernfactor' : ValueOption(
				name='nested-blobkernfactor',
				value='',
				value_type=float, 
				description='Nested blob curvature/LoG kernel size factor f (kern size=f x sigma) (default=1)',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				advanced=True,
				default_value=1.,
				min_value=0.,
				max_value=1000.
			),

			# == SOURCE FITTING OPTIONS ==
			'fitsources' : Option(
				name='fitsources', 
				description='Fit compact point-like sources found (default=false)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-usethreads' : Option(
				name='fit-usethreads', 
				description='Enable multithread in source fitting (NB: use Minuit2 minimizer if enabled) (default=disabled)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			#'fit-minimizer' : ValueOption(
			#	name='fit-minimizer',
			#	value='',
			#	value_type=str, 
			#	description='Fit minimizer {Minuit,Minuit2} (default=Minuit2)',
			#	category='COMPACT-SOURCES',
			#	subcategory='FITTING',
			#	advanced=True,
			#	default_value='Minuit2',
			#	min_value='',
			#	max_value=''
			#),
			'fit-minimizer' : EnumValueOption(
				name='fit-minimizer',
				value='',
				value_type=str, 
				description='Fit minimizer',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value='Minuit2',
				allowed_values=['Minuit','Minuit2']
			),
			#'fit-minimizeralgo' : ValueOption(
			#	name='fit-minimizeralgo',
			#	value='',
			#	value_type=str, 
			#	description='Fit minimizer algo {migrad,simplex,minimize,scan,fumili (Minuit2)} (default=minimize)',
			#	category='COMPACT-SOURCES',
			##	subcategory='FITTING',
			#	advanced=True,
			#	default_value='minimize',
			#	min_value='',
			#	max_value=''
			#),
			'fit-minimizeralgo' : EnumValueOption(
				name='fit-minimizeralgo',
				value='',
				value_type=str, 
				description='Fit minimizer algo {migrad,simplex,minimize,scan,fumili (Minuit2)} (default=minimize)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value='minimize',
				allowed_values=['migrad','simplex','minimize','scan','fumili']
			),

			'fit-printlevel' : ValueOption(
				name='fit-printlevel',
				value='',
				value_type=int, 
				description='Fit print level (default=1)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=0,
				min_value=0,
				max_value=3
			),
			'fit-strategy' : ValueOption(
				name='fit-strategy',
				value='',
				value_type=int, 
				description='Fit strategy (default=2)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=2,
				min_value=0,
				max_value=3
			),
			'fit-maxnbeams' : ValueOption(
				name='fit-maxnbeams',
				value='',
				value_type=int, 
				description='Maximum number of beams for fitting if compact source (default=20)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=20,
				min_value=0,
				max_value=100000
			),
			'fit-maxcomponents' : ValueOption(
				name='fit-maxcomponents',
				value='',
				value_type=int, 
				description='Maximum number of components fitted in a blob (default=3)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=3,
				min_value=0,
				max_value=100
			),
			'fit-usenestedascomponents' : Option(
				name='fit-usenestedascomponents', 
				description='Initialize fit components to nested sources found in source (default=no)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-freebkg' : Option(
				name='fit-freebkg', 
				description='Fit with bkg offset parameter free to vary (default=fixed)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-estimatedbkg' : Option(
				name='fit-estimatedbkg', 
				description='Set bkg par starting value to estimated bkg (average over source pixels by default, box around source if --fit-estimatedboxbkg is given) (default=use fixed bkg start value)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-usebkgboxestimate' : Option(
				name='fit-usebkgboxestimate', 
				description='Set bkg par starting value to estimated bkg (from box around source)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-bkg' : ValueOption(
				name='fit-bkg',
				value='',
				value_type=float, 
				description='Bkg par starting value (NB: ineffective when -fit-estimatedbkg is enabled) (default=0)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=0.,
				min_value=-1.e+6,
				max_value=1.e+6
			),
			'fit-ampllimit' : ValueOption(
				name='fit-ampllimit',
				value='',
				value_type=float, 
				description='Limit amplitude range par (Speak*(1+-FIT_AMPL_LIMIT)) (default=0.3)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=0.3,
				min_value=0.,
				max_value=2.
			),
			'prefit-freeampl' : Option(
				name='prefit-freeampl', 	
				description='Set free amplitude par in pre-fit (default=fixed)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-sigmalimit' : ValueOption(
				name='fit-sigmalimit',
				value='',
				value_type=float, 
				description='Gaussian sigma limit around psf or beam (Bmaj*(1+-FIT_SIGMA_LIMIT)) (default=0.3)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=0.3,
				min_value=0.,
				max_value=2.
			),
			'fit-thetalimit' : ValueOption(
				name='fit-thetalimit',
				value='',
				value_type=float, 
				description='Gaussian theta limit around psf or beam in degrees (e.g. Bpa +- FIT_THETA_LIMIT) (default=90)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=90.,
				min_value=0.,
				max_value=360.
			),
			'fit-nobkglimits' : Option(
				name='fit-nobkglimits', 
				description='Do not apply limits in bkg offset parameter in fit (default=fit with limits when par is free)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-noampllimits' : Option(
				name='fit-noampllimits', 
				description='Do not apply limits in Gaussian amplitude parameters in fit (default=fit with limits)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-nosigmalimits' : Option(
				name='fit-nosigmalimits', 
				description='Do not apply limits in Gaussian sigma parameters in fit (default=fit with limits)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-noposlimits' : Option(
				name='fit-noposlimits', 
				description='Do not apply limits in Gaussian mean parameters in fit (default=fit with limits)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-poslimit' : ValueOption(
				name='fit-poslimit',
				value='',
				value_type=int, 
				description='Source centroid limits in pixel (default=3)',	
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=3,
				min_value=0,
				max_value=1000
			),
			'prefit-freepos' : Option(
				name='prefit-freepos', 
				description='Set free centroid pars in pre-fit (default=fixed)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-nothetalimits' : Option(
				name='fit-nothetalimits', 
				description='Do not apply limits in Gaussian ellipse pos angle parameters in fit (default=fit with limits)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-fixsigma' : Option(
				name='fit-fixsigma',
				description='Fit with sigma parameters fixed to start value (beam bmaj/bmin) (default=fit with sigma free and constrained)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'prefit-fixsigma' : Option(
				name='prefit-fixsigma', 
				description='Fix sigma parameters in pre-fit (default=free)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-fixtheta' : Option(
				name='fit-fixtheta', 
				description='Fit with theta parameters fixed to start value (beam bpa) (default=fit with theta free and constrained)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'prefit-fixtheta' : Option(
				name='prefit-fixtheta', 
				description='Fix theta parameter in pre-fit (default=free)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-peakminkern' : ValueOption(
				name='fit-peakminkern',
				value='',
				value_type=int, 
				description='Minimum dilation kernel size (in pixels) used to detect peaks (default=3)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=3,
				min_value=0,
				max_value=100
			),
			'fit-peakmaxkern' : ValueOption(
				name='fit-peakmaxkern',
				value='',
				value_type=int, 
				description='Maximum dilation kernel size (in pixels) used to detect peaks (default=7)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=7,
				min_value=0,
				max_value=100
			),
			'fit-peakmultiplicitythr' : ValueOption(
				name='fit-peakmultiplicitythr',
				value='',
				value_type=int, 
				description='Requested peak multiplicity across different dilation kernels (-1=peak found in all given kernels,1=only in one kernel, etc) (default=1)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=1,
				min_value=-1,
				max_value=100
			),
			'fit-peakshifttol' : ValueOption(
				name='fit-peakshifttol',
				value='',
				value_type=int, 
				description='Shift tolerance (in pixels) used to compare peaks in different dilation kernels (default=2 pixels)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=2,
				min_value=0,
				max_value=20
			),
			'fit-peakzthrmin' : ValueOption(
				name='fit-peakzthrmin',
				value='',
				value_type=float, 
				description='Minimum peak flux significance (in nsigmas above avg source bkg & noise) below which peak is skipped (default=1)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=1.,
				min_value=0.,
				max_value=1000.
			),
			'fit-fcntol' : ValueOption(
				name='fit-fcntol',	
				value='',
				value_type=float, 
				description='Fit function tolerance for convergence (default 1.e-2)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=1.e-2,
				min_value=0.,
				max_value=100.
			),
			'fit-maxniters' : ValueOption(
				name='fit-maxniters',
				value='',
				value_type=int, 
				description='Maximum number of fit iterations or function calls performed (default 10000)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=10000,
				min_value=0,
				max_value=1000000
			),
			'fit-noimproveconvergence' : Option(
				name='fit-noimproveconvergence', 
				description='Do not use iterative fitting to try to achieve fit convergence (default=use)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-noretry' : Option(
				name='fit-noretry', 
				description='Do not iteratively retry fit with less components in case of failed convergence (default=retry)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-nretries' : ValueOption(
				name='fit-nretries',
				value='',
				value_type=int, 
				description='Maximum number of fit retries if fit failed or has parameters at bound (default 10)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=10,
				min_value=0,
				max_value=100000
			),
			'fit-parboundincreasestep' : ValueOption(
				name='fit-parboundincreasestep',
				value='',
				value_type=float, 
				description='Fit par bound increase step size (e.g. parmax= parmax_old+(1+nretry)*fitParBoundIncreaseStepSize*0.5*|max-min|). Used in iterative fitting. (default=0.1)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=0.1,
				min_value=0.,
				max_value=10.
			),
			'fit-improveerrors' : Option(
				name='fit-improveerrors', 
				description='Run final minimizer step (e.g. HESS) to improve fit error estimates (default=no)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',	
				advanced=True
			),
			'fit-scaledatatomax' : Option(
				name='fit-scaledatatomax', 
				description='Scale source data to max pixel flux for fitting. Otherwise scale to mJy (default=no)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),
			'fit-nochi2cut' : Option(
				name='fit-nochi2cut', 
				description='Do not apply reduced chi2 cut to fitted sources (default=apply)',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-chi2cut' : ValueOption(
				name='fit-chi2cut',
				value='',
				value_type=float, 
				description='Chi2 cut value (default=5)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=5.,
				min_value=0.,
				max_value=1000.
			),
			'fit-useellipsecuts' : Option(
				name='fit-useellipsecuts', 
				description='Apply ellipse cuts to fitted sources (default=not applied)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True
			),

			# == SOURCE RESIDUAL OPTIONS ==
			'computeresiduals' : Option(
				name='computeresiduals', 
				description='Compute compact source residual map (after compact source search)',
				category='IMGRES'
			),
			'res-removenested' : Option(
				name='res-removenested', 
				description='When a source has nested sources remove only on nested (default=false)',
				category='IMGRES'
			),
			'res-zthr' : ValueOption(
				name='res-zthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used to dilate sources (default=5 sigmas)',
				category='IMGRES',
				default_value=5.,
				min_value=0.,
				max_value=10000.
			),
			'res-zhighthr' : ValueOption(
				name='res-zhighthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used to dilate sources (even if they have nested components or different dilation type) (default=10 sigmas)',
				category='IMGRES',
				default_value=10.,
				min_value=0.,
				max_value=10000.
			),
			'dilatekernsize' : ValueOption(
				name='dilatekernsize',
				value='',
				value_type=int, 
				description='Size of dilating kernel in pixels (default=9)',
				category='IMGRES',
				default_value=9,
				min_value=1,
				max_value=1001
			),
			#'res-removedsourcetype' : ValueOption(
			#	name='res-removedsourcetype',
			#	value='',
			#	value_type=int, 
			#	description='Type of source dilated from the input image (-1=ALL,1=COMPACT,2=POINT-LIKE,3=EXTENDED) (default=2)',
			#	category='IMGRES',
			#	default_value=2,
			#	min_value=-1,
			#	max_value=3
			#),
			'res-removedsourcetype' : EnumValueOption(
				name='res-removedsourcetype',
				value='',
				value_type=str, 
				description='Type of source dilated from the input image',
				category='IMGRES',
				default_value='POINT-LIKE',
				allowed_values=['ALL','COMPACT','POINT-LIKE','EXTENDED']
			),
			#'res-pssubtractionmethod' : ValueOption(
			#	name='res-pssubtractionmethod',
			#	value='',
			#	value_type=int, 
			#	description='Method used to subtract point-sources in residual map (1=DILATION, 2=FIT MODEL REMOVAL)',
			#	category='IMGRES',
			#	default_value=1,
			#	min_value=1,
			#	max_value=2
			#),
			'res-pssubtractionmethod' : EnumValueOption(
				name='res-pssubtractionmethod',
				value='',
				value_type=str, 
				description='Method used to subtract point-sources in residual map',
				category='IMGRES',
				default_value='DILATION',
				allowed_values=['DILATION','FITMODEL']
			),
			'res-bkgaroundsource': Option(
				name='res-bkgaroundsource', 
				description='Use bkg computed around source rather than the one computed using the global/local bkg map (default=false)',	
				category='IMGRES'
			),

			# == SMOOTHING FILTER OPTIONS ==
			'no-presmoothing' : Option(	
				name='no-presmoothing', 
				description='Do not smooth input/residual map before extended source search (default=yes)',
				category='IMGSMOOTH'
			),
			#'smoothfilter' : ValueOption(
			#	name='smoothfilter',
			#	value='',
			#	value_type=int, 
			#	description='Smoothing filter to be used (1=gaussian, 2=guided filter) (default=2)',
			#	category='IMGSMOOTH',
			#	default_value=2,
			#	min_value=1,
			#	max_value=2
			#),
			'smoothfilter' : EnumValueOption(
				name='smoothfilter',
				value='',
				value_type=str, 
				description='Smoothing filter to be used',
				category='IMGSMOOTH',
				default_value='GUIDED',
				allowed_values=['GAUSSIAN','GUIDED']
			),
			'guidedfilter-radius' : ValueOption(
				name='guidedfilter-radius',	
				value='',
				value_type=float, 
				description='Guided filter radius par (default=12)',
				category='IMGSMOOTH',
				default_value=12.,
				min_value=0.,
				max_value=1000.
			),
			'guidedfilter-eps' : ValueOption(
				name='guidedfilter-eps',
				value='',
				value_type=float, 
				description='Guided filter eps par (default=0.04)',
				category='IMGSMOOTH',
				default_value=0.04,
				min_value=0.,
				max_value=1000.
			),

			# == EXTENDED SOURCE SEARCH OPTIONS ==
			'no-extendedsearch' : Option(
				name='no-extendedsearch', 
				description='Do not search extended sources',
				category='EXTENDED-SOURCES'
			),
			#'extsfinder' : ValueOption(
			#	name='extsfinder',
			#	value='',
			#	value_type=int, 
			#	description='Extended source search method {1=WT-thresholding,2=SPSegmentation,3=ActiveContour,4=Saliency thresholding} (default=4)',	
			#	category='EXTENDED-SOURCES',
			#	default_value=4,
			#	min_value=1,
			#	max_value=4
			#),
			'extsfinder' : EnumValueOption(
				name='extsfinder',
				value='',
				value_type=str, 
				description='Extended source search method',	
				category='EXTENDED-SOURCES',
				default_value='SALIENCY-THRESH',
				allowed_values=['WT-THRESH','SP-HIERCLUST','ACTIVE-CONTOUR','SALIENCY-THRESH']
			),
			#'activecontour' : ValueOption(
			#	name='activecontour',
			#	value='',
			#	value_type=int, 
			#	description='Active contour method {1=Chanvese, 2=LRAC} (default=1)',
			#	category='EXTENDED-SOURCES',
			#	default_value=1,
			#	min_value=1,
			#	max_value=2
			#),
			'activecontour' : EnumValueOption(
				name='activecontour',
				value='',
				value_type=str, 
				description='Active contour method',
				category='EXTENDED-SOURCES',
				default_value='CHANVESE',
				allowed_values=['CHANVESE','LRAC']
			),

			# == SALIENCY FILTER OPTIONS ==
			'sp-size' : ValueOption(
				name='sp-size',
				value='',
				value_type=int, 
				description='Superpixel size (in pixels) used in hierarchical clustering (default=20)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=20,
				min_value=5,
				max_value=10000
			),
			'sp-beta' : ValueOption(
				name='sp-beta',
				value='',
				value_type=float, 
				description='Superpixel regularization par (beta) used in hierarchical clustering (default=1)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=1,
				min_value=1.e-10,
				max_value=1.e+10
			),
			'sp-minarea' : ValueOption(
				name='sp-minarea',
				value='',
				value_type=int, 
				description='Superpixel min area (in pixels) used in hierarchical clustering (default=10)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=10,
				min_value=1,
				max_value=10000
			),
			'saliency-nooptimalthr' : Option(
				name='saliency-nooptimalthr', 	
				description='Do not use optimal threshold in multiscale saliency estimation (e.g. use median thr) (default=use optimal)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY'
			),
			'saliency-thr' : ValueOption(
				name='saliency-thr',
				value='',
				value_type=float, 
				description='Saliency map threshold factor wrt optimal/median threshold (default=2.8)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=2.8,
				min_value=0.,
				max_value=10.
			),
			'saliency-minreso' : ValueOption(
				name='saliency-minreso',
				value='',
				value_type=int, 
				description='Superpixel size (in pixels) used in multi-reso saliency map smallest scale (default=20 pixels)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=20,
				min_value=1,
				max_value=1000
			),
			'saliency-maxreso' : ValueOption(
				name='saliency-maxreso',
				value='',
				value_type=int, 
				description='Superpixel size (in pixels) used in multi-reso saliency map highest scale (default=60 pixels)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=60,
				min_value=1,
				max_value=1000
			),
			'saliency-resostep' : ValueOption(
				name='saliency-resostep',
				value='',
				value_type=int, 
				description='Superpixel size step (in pixels) used in multi-reso saliency map computation (default=10 pixels)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=10,
				min_value=1,
				max_value=100
			),
			'saliency-nn' : ValueOption(
				name='saliency-nn',
				value='',
				value_type=float, 
				description='Fraction of most similar region neighbors used in saliency map computation (default=1)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True,
				default_value=1.,
				min_value=0,
				max_value=1.
			),
			'saliency-usebkgmap' : Option(
				name='saliency-usebkgmap', 
				description='Use bkg map in saliency computation (default=not used)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True
			),
			'saliency-usermsmap' : Option(
				name='saliency-usermsmap', 
				description='Use noise map in saliency computation (default=not used)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True
			),
			'saliency-userobustpars' : Option(
				name='saliency-userobustpars', 
				description='Use robust pars in saliency computation (default=no)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY'
			),

			# == ACTIVE-CONTOUR MAIN OPTIONS ==
			'ac-niters' : ValueOption(
				name='ac-niters',	
				value='',
				value_type=int, 
				description='Maximum number of iterations in active-contour algorithms (default=1000)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=1000,
				min_value=1,
				max_value=100000
			),
			#'ac-levelset' : ValueOption(
			#	name='ac-levelset',
			#	value='',
			#	value_type=int,
			#	description='Init level set method in active-contour algorithms (1=circle,2=checkerboard,3=saliency) (default=1)',
			#	category='EXTENDED-SOURCES',
			#	subcategory='ACTIVE-CONTOUR',
			#	default_value=1,
			#	min_value=1,
			#	max_value=3
			#),
			'ac-levelset' : EnumValueOption(
				name='ac-levelset',
				value='',
				value_type=str,
				description='Init level set method in active-contour algorithms',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value='CIRCLE',
				allowed_values=['CIRCLE','CHECKERBOARD','SALIENCY']
			),
			'ac-levelsetsize' : ValueOption(
				name='ac-levelsetsize',
				value='',
				value_type=float, 
				description='Init level set size par in active-contour algorithms (default=0.1ximage size)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=0.1,
				min_value=0.,
				max_value=1.
			),
			'ac-tolerance' : ValueOption(
				name='ac-tolerance',
				value='',
				value_type=float,
				description='Tolerance par in active-contour algorithms (default=0.1)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=0.1,
				min_value=0.,
				max_value=1.
			),

			# == CHAN-VESE OPTIONS ==
			'cv-nitersinner' : ValueOption(
				name='cv-nitersinner',
				value='',
				value_type=int,	
				description='Maximum number of inner iterations in ChanVese algorithm (default=1000)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				advanced=True,
				default_value=5,
				min_value=0,
				max_value=100000
			),
			'cv-nitersreinit' : ValueOption(
				name='cv-nitersreinit',	
				value='',
				value_type=int,
				description='Maximum number of re-init iterations in ChanVese algorithm (default=1000)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				advanced=True,
				default_value=5,
				min_value=0,
				max_value=100000
			),
			'cv-timestep' : ValueOption(
				name='cv-timestep',
				value='',
				value_type=float,
				description='Chan-Vese time step parameter (default=0.007)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=0.007,
				min_value=0.,
				max_value=1000.
			),
			'cv-wsize' : ValueOption(
				name='cv-wsize',
				value='',
				value_type=float,
				description='Chan-Vese window size parameter (default=1)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=1.,
				min_value=0.,
				max_value=1000.
			),
			'cv-lambda1' : ValueOption(
				name='cv-lambda1',
				value='',
				value_type=float,
				description='Chan-Vese lambda1 parameter (default=1)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=1.,
				min_value=0.,
				max_value=100.
			),
			'cv-lambda2' : ValueOption(
				name='cv-lambda2',
				value='',
				value_type=float,
				description='Chan-Vese lambda2 parameter (default=2)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=2.,
				min_value=0.,
				max_value=100.
			),
			'cv-mu' : ValueOption(
				name='cv-mu',
				value='',
				value_type=float,
				description='Chan-Vese mu parameter (default=0.5)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=0.5,
				min_value=0.,
				max_value=100.
			),
			'cv-nu' : ValueOption(	
				name='cv-nu',
				value='',
				value_type=float,
				description='Chan-Vese nu parameter (default=0)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=0.,
				min_value=0.,
				max_value=100.
			),
			'cv-p' : ValueOption(
				name='cv-p',
				value='',
				value_type=float,
				description='Chan-Vese p parameter (default=1)',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=1.,
				min_value=0.,
				max_value=100.
			),

			# == WAVELET TRANSFORM FILTER OPTIONS ==
			'wtscalemin' : ValueOption(
				name='wtscalemin',
				value='',
				value_type=int,
				description='Minimum Wavelet Transform scale for extended source search (default=3)',
				category='EXTENDED-SOURCES',
				subcategory='WAVELET-TRANSFORM',
				default_value=3,
				min_value=1,
				max_value=10
			),
			'wtscalemax' : ValueOption(
				name='wtscalemax',
				value='',
				value_type=int,
				description='Maximum Wavelet Transform scale for extended source search (default=6)',
				category='EXTENDED-SOURCES',
				subcategory='WAVELET-TRANSFORM',
				default_value=6,
				min_value=1,
				max_value=10
			),

			# == RUN OPTIONS ==
			#'run' : Option('run', description='Run the generated run script on the local shell. If disabled only run script will be generated for later run',category='RUN'),
			#'envfile' : ValueOption('envfile','',str, description='File (.sh) with list of environment variables to be loaded by each processing node',category='RUN'),
			#'maxfiles' : ValueOption('maxfiles','',int, description='Maximum number of input files processed in filelist (default=-1=all files)',category='RUN'),
			#'addrunindex' : Option('addrunindex', description='Append a run index to submission script (in case of list execution) (default=no)',category='RUN'),
			#'jobdir' : ValueOption('jobdir','',str, description='Job directory where to run (default=pwd)',category='RUN'),			
			#'outdir' : ValueOption('outdir','',str, description='Output directory where to put run output file (default=pwd)',category='RUN'),
			#'mpioptions' : ValueOption('mpioptions','',str, description='Options to be passed to MPI (e.g. --bind-to {none,hwthread, core, l1cache, l2cache, l3cache, socket, numa, board}) (default=none)',category='RUN'),
			#'hostfile' : ValueOption('hostfile','',str, description='Ascii file with list of hosts used by MPI (default=no hostfile used)',category='RUN'),
			#'containerrun' : Option('containerrun', description='Run inside Caesar container',category='RUN'),
			#'containerimg' : ValueOption('containerimg','',str, description='Singularity container image file (.simg) with CAESAR installed software',category='RUN'),
			#'containeroptions' : ValueOption('containeroptions','',str, description='Options to be passed to container run (e.g. -B /home/user:/home/user) (default=none)',category='RUN'),

			#'loglevel' : ValueOption(
			#	name='loglevel',
			#	value='',
			#	value_type=str, 
			#	description='Logging level string {INFO, DEBUG, WARN, ERROR, OFF} (default=INFO)',
			#	category='RUN',
			#	default_value='INFO',
			#	min_value='',
			#	max_value=''
			#),
			'loglevel' : EnumValueOption(
				name='loglevel',
				value='',
				value_type=str, 
				description='Logging level value',
				category='RUN',
				default_value='INFO',
				allowed_values=['INFO', 'DEBUG', 'WARN', 'ERROR', 'OFF']
			),
			'no-logredir' : Option(
				name='no-logredir', 
				description='Do not redirect logs to output file in script',
				category='RUN'
			),
			'no-mpi' : Option(
				name='no-mpi', 
				description='Disable MPI run (even with 1 proc) (default=enabled)',
				category='RUN'
			),
			'nproc' : ValueOption(
				name='nproc',
				value='',
				value_type=int, 
				description='Number of MPI processors per node used (NB: mpi tot nproc=nproc x nnodes) (default=1)',
				category='RUN',
				default_value=1,
				min_value=1,
				max_value=1000
			),
			'nthreads' : ValueOption(
				name='nthreads',
				value='',
				value_type=int, 
				description='Number of threads to be used in OpenMP (default=-1=all available in node)',
				category='RUN',
				default_value=1,
				min_value=-1,
				max_value=1000
			),
			
			# == SFINDER SUBMISSION OPTIONS ==
			#'submit' : Option('submit', description='Submit the script to the batch system using queue specified. Takes precedence over local run.',category='RUN'),
			#'batchsystem' : ValueOption('batchsystem','',str, description='Name of batch system. Valid choices are {PBS,SLURM} (default=PBS)',category='RUN'),
			#'queue' : ValueOption('queue','',str, description='Name of queue in batch system',category='RUN'),
			#'jobwalltime' : ValueOption('jobwalltime','',str, description='Job wall time in batch system (default=96:00:00)',category='RUN'),
			#'jobcpus' : ValueOption('jobcpus','',int, description='Number of cpu per node requested for the job (default=1)',category='RUN'),
			#'jobnodes' : ValueOption('jobnodes','',int, description='Number of nodes requested for the job (default=1)',category='RUN'),
			#'jobmemory' : ValueOption('jobmemory','',float, description='Memory in GB required for the job (default=4)',category='RUN'),
			#'jobusergroup' : ValueOption('jobusergroup','',str, description='Name of job user group batch system (default=empty)',category='RUN'),

			# == PARALLEL PROCESSING OPTIONS ==
			'tilesize' : ValueOption(
				name='tilesize',
				value='',
				value_type=int, 
				description='Size (in pixels) of tile used to partition input image in distributed processing (default=0=no tile split)', 
				category='RUN',
				default_value=0.,
				min_value=0.,
				max_value=10000000.
			),
			'tilestep' : ValueOption(
				name='tilestep',
				value='',
				value_type=float, 
				description='Tile step size (range 0-1) expressed as tile fraction used in tile overlap (default=1=no overlap)',
				category='RUN',
				default_value=1.,
				min_value=0.001,
				max_value=1.
			),
			'mergeedgesources' : Option(
				name='mergeedgesources', 
				description='Merge sources at tile edges. NB: Used for multitile processing. (default=no)',
				category='RUN'
			),
			'no-mergesources' : Option(
				name='no-mergesources', 
				description='Disable source merging in each tile (default=enabled)',
				category='RUN'
			),


		} # close dict

		# - Define option value transformers
		self.option_value_transformer= {
			#	'inputfile': self.transform_inputfile
			'regionwcs': self.transform_regionwcs,
			'bkgestimator': self.transform_bkgestimator,
			'blobmaskmethod': self.transform_blobmaskmethod,
			'res-removedsourcetype': self.transform_resremovedsourcetype,
			'res-pssubtractionmethod': self.transform_respssubtractionmethod,
			'smoothfilter': self.transform_smoothfilter,
			'extsfinder': self.transform_extsfinder,
			'activecontour': self.transform_activecontour,
			'ac-levelset': self.transform_aclevelset
		}

		# - Fill some default cmd args
		logger.debug("Adding some options by default ...", action="submitjob")
		self.cmd_args.append("--run")
		self.cmd_args.append("--save-summaryplot")
		self.cmd_args.append("--save-regions ")

	
	def set_data_input_option_value(self):
		""" Set app input option value """

		input_opt= "".join("--inputfile=%s" % self.data_inputs)
		self.cmd_args.append(input_opt)


	def set_ncores_from_options(self):
		""" Returns the number of cores from parsed options (to be overridden) """
		
		# - Search if --nthreads option was given and extract value
		matching= [s for s in self.cmd_args if "--nthreads" in s]
		self.run_options["ncores"]= 1
		if matching:
			parsed_option_vals= matching[0].split('=')
			if len(parsed_option_vals)==2:
				try:
					nthreads= int(parsed_option_vals[1])
					if nthreads>0:						
						self.run_options["ncores"]= nthreads
						logger.info("Set job ncores to %d ..." % self.run_options["ncores"], action="submitjob")
					else:
						logger.warn("Parsed nthreads value (%d) is <=0, setting ncores=1 ..." % nthreads, action="submitjob")
				except:
					logger.warn("Failed to parse nthreads option, setting ncores=1 ...", action="submitjob")			
			else:
				logger.warn("Expected 2 fields when parsing nthreads option, setting ncores=1 ...", action="submitjob")

	def set_nproc_from_options(self):
		""" Returns the number of MPI proc from parsed options (to be overridden) """
		
		# - Search if --nproc option was given and extract value
		matching= [s for s in self.cmd_args if "--nproc" in s]
		self.run_options["nproc"]= 1
		if matching:
			parsed_option_vals= matching[0].split('=')
			if len(parsed_option_vals)==2:
				try:
					nproc= int(parsed_option_vals[1])
					if nproc>0:						
						self.run_options["nproc"]= nproc
						logger.info("Set job MPI proc to %d ..." % self.run_options["nproc"], action="submitjob")
					else:
						logger.warn("Parsed nproc value (%d) is <=0, setting nproc=1 ..." % nproc, action="submitjob")
				except:
					logger.warn("Failed to parse nproc option, setting nproc=1 ...", action="submitjob")			
			else:
				logger.warn("Expected 2 fields when parsing nproc option, setting nproc=1 ...", action="submitjob")

	def transform_regionwcs(self,regionwcs_str):
		""" Transform regionwcs from enum to code """	

		regionwcs_map= {
			"J2000": "0",
			"B1950": "1",
			"GALACTIC": "2"
		}
		return regionwcs_map[regionwcs_str]


	def transform_bkgestimator(self,bkgestimator_str):
		""" Transform bkgestimator from enum to code """	

		bkgestimator_map= {
			"Mean": "1",
			"Median": "2",
			"BiWeight": "3",
			"ClippedMedian": "4"
		}
		return bkgestimator_map[bkgestimator_str]
	
		
	def transform_blobmaskmethod(self,blobmaskmethod_str):
		""" Transform blobmaskmethod from enum to code """	

		blobmaskmethod_map= {
			"GausLaplacian": "1",
			"MultiScaleLoG": "2",
		}
		return blobmaskmethod_map[blobmaskmethod_str]


	def transform_resremovedsourcetype(self,resremovedsourcetype_str):
		""" Transform resremovedsourcetype from enum to code """	

		resremovedsourcetype_map= {
			"ALL": "-1",
			"COMPACT": "1",
			"POINT-LIKE": "2",
			"EXTENDED": "3",
		}
		return resremovedsourcetype_map[resremovedsourcetype_str]

	def transform_respssubtractionmethod(self,respssubtractionmethod_str):
		""" Transform respssubtractionmethod from enum to code """	

		respssubtractionmethod_map= {
			"DILATION": "1",
			"FITMODEL": "2"
		}
		return respssubtractionmethod_map[respssubtractionmethod_str]

	def transform_smoothfilter(self,smoothfilter_str):
		""" Transform smoothfilter from enum to code """	

		smoothfilter_map= {
			"GAUSSIAN": "1",
			"GUIDED": "2"
		}
		return smoothfilter_map[smoothfilter_str]

	def transform_extsfinder(self,extsfinder_str):
		""" Transform extsfinder from enum to code """	

		extsfinder_map= {
			"WT-THRESH": "1",
			"SP-HIERCLUST": "2",
			"ACTIVE-CONTOUR": "3",
			"SALIENCY-THRESH": "4"
		}
		return extsfinder_map[extsfinder_str]

	def transform_activecontour(self,activecontour_str):
		""" Transform activecontour from enum to code """	

		activecontour_map= {
			"CHANVESE": "1",
			"LRAC": "2",
		}
		return activecontour_map[activecontour_str]

	def transform_aclevelset(self,aclevelset_str):
		""" Transform aclevelset from enum to code """	

		aclevelset_map= {
			"CIRCLE": "1",
			"CHECKERBOARD": "2",
			"SALIENCY": "3"
		}
		return aclevelset_map[aclevelset_str]



	def transform_inputfile(self,file_uuid):
		""" Transform input file from uuid to actual path """		
	
		# - Get aai info
		username= 'anonymous'
		if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
			email= g.oidc_token_info['email']
			username= utils.sanitize_username(email)

		# - Inspect inputfile (expect it is a uuid, so convert to filename)
		logger.info("Finding inputfile uuid %s ..." % file_uuid, action="submitjob")
		collection_name= username + '.files'

		file_path= ''
		try:
			data_collection= mongo.db[collection_name]
			item= data_collection.find_one({'fileid': str(file_uuid)})
			if item and item is not None:
				file_path= item['filepath']
			else:
				logger.warn("File with uuid=%s not found in DB!" % file_uuid, action="submitjob")
				file_path= ''
		except Exception as e:
			logger.error("Exception (err=%s) catch when searching file in DB!" % str(e), action="submitjob")
			return ''
		
		if not file_path or file_path=='':
			logger.warn("inputfile uuid %s is empty or not found in the system!" % file_uuid, action="submitjob")
			return ''

		logger.info("inputfile uuid %s converted in %s ..." % (file_uuid,file_path), action="submitjob")

		return file_path
		
