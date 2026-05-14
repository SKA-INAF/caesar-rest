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

	def __init__(self, app_name="caesar"):
		""" Return caesar sfinder app configurator class """
		AppConfigurator.__init__(self, app_name=app_name)

		# - Define cmd name
		self.cmd= 'SFinderSubmitter.sh'
		self.cmd_args= []
		self.batch_processing_support= True

		# - Describe app
		self.description = (
			"Run a source finder tool on astronomical radio-continuum images. "
			"The tool supports both point-like/compact and extended source extraction. "
			"It also supports measurement of point-like/compact source and nested component parameters (flux density, position, extension, morphological flags) through 2D gaussian mixture fitting. "
			"The app expects input image-like astronomical data, in either FITS or PNG format. "
		)
		
		self.input_requirements = {
			"supported_formats": ["fits"],
			"expected_data": "Single astronomical image suitable for source detection.",
			"notes": [
				"The method is most suited for radio-continuum images."
			]
		}
		
		self.limitations = [
			"Compact source detection quality depends on background estimation parameters and detection thresholds.",
			"Extended source detection quality depends on background estimation parameters and on the extended source detection algorithm chosen."
			"Processing of very large images (>10000 pixels) is supported but it may be computationally expensive unless the tiling and parallel run mode is activated (see options).",
			"The app can in principle be used to detect sources in astronomical images (FITS) from other domains (e.g. optical, infrared, gamma-rays) but we anticipate sub-optimal performance as the tool was specifically tested on radio images and relative image metadata only."
		]

		# - Define dictionary with allowed options
		self.valid_options= {
			# == INPUT OPTIONS ==
			#'inputfile' : ValueOption('inputfile','',str,True),
			#'filelist' : ValueOption('filelist','',True),
		
			# == OUTPUT OPTIONS ==
			'save-fits' : Option(
				name='save-fits', 
				description='Save maps in FITS format (default: ROOT format)', 
				category='OUTPUT',
				default_value=False
			),
			'save-inputmap' : Option(
				name='save-inputmap', 
				description='Save input map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-bkgmap' : Option(
				name='save-bkgmap', 
				description='Save bkg map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-rmsmap' : Option(
				name='save-rmsmap', 
				description='Save rms map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-significancemap' : Option(
				name='save-significancemap', 
				description='Save significance map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-residualmap' : Option(
				name='save-residualmap', 
				description='Save residual map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-saliencymap' : Option(
				name='save-saliencymap', 	
				description='Save saliency map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-segmentedmap' : Option(
				name='save-segmentedmap', 
				description='Save segmented map in output file', 
				category='OUTPUT',
				default_value=False
			),
			'save-regions' : Option(
				name='save-regions', 
				description='Save DS9 regions', 
				category='OUTPUT',
				default_value=True
			),
			'save-summaryplot' : Option(
				name='save-summaryplot', 
				description='Save summary plot image+detections', 
				category='OUTPUT',
				default_value=True
			),
			'save-catalog-to-json' : Option(
				name='save-catalog-to-json', 
				description='Save catalog of detected sources in JSON format', 
				category='OUTPUT',
				default_value=True
			),
			'convertregionstowcs' : Option(
				name='convertregionstowcs', 
				description='Save DS9 regions in WCS format', 
				category='OUTPUT', 
				advanced=True,
				default_value=False
			),
			'regionwcs' : EnumValueOption(
				name='regionwcs',
				value='',
				value_type=str, 
				description='DS9 region WCS output format', 
				category='OUTPUT', 
				advanced=True,
				default_value='J2000',
				allowed_values=['J2000', 'B1950', 'GALACTIC']
			),

			
			# == IMG READ OPTIONS ==
			'read-subimg' : Option(
				name='read-subimg', 
				description='Read sub-image of input image in [xmin,xmax] [ymin,ymax] range (default=read full image)',
				category='IMGREAD',
				default_value=False
			),
			'xmin' : ValueOption(
				name='xmin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel x=xmin (0: read full image)',
				category='IMGREAD',
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'xmax' : ValueOption(
				name='xmax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel x=xmax (0: read full image)',
				category='IMGREAD',	
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'ymin' : ValueOption(
				name='ymin',
				value='',
				value_type=int, 
				description='Read sub-image of input image starting from pixel y=xmin (0: read full image)',
				category='IMGREAD',	
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),
			'ymax' : ValueOption(
				name='ymax',
				value='',
				value_type=int, 
				description='Read sub-image of input image up to pixel y=ymax (0: read full image)',
				category='IMGREAD',
				default_value=0,
				min_value=-1000000,
				max_value=1000000
			),

			# == STATS OPTIONS ==		
			'no-parallelmedian' : Option(
				name='no-parallelmedian', 
				description='Switch off parallel median algorithm',
				category='IMGSTATS',
				advanced=True,
				default_value=False
			),

			# == BKG OPTIONS ==		
			'bmaj' : ValueOption(
				name='bmaj',
				value='',
				value_type=float, 
				description='User-supplied beam Bmaj in arcsec (NB: used only when beam info is not available in input map)',
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
				description='User-supplied beam Bmin in arcsec (NB: used only when beam info is not available in input map)',
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
				description='User-supplied beam position angle in degrees (NB: used only when beam info is not available in input map)',
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
				description='Map pixel size in arcsec (NB: used only when info is not available in input map)',
				category='IMGBKG',
				advanced=True,
				default_value=1,
				min_value=0,
				max_value=3600
			),
			'globalbkg' : Option(
				name='globalbkg', 
				description='Use global bkg (default: use local bkg)',
				category='IMGBKG',
				default_value=False
			),
			'bkgestimator' : EnumValueOption(
				name='bkgestimator',
				value='',
				value_type=str, 
				description='Stat estimator used for computing the map bkg',
				category='IMGBKG',
				default_value="Median",
				allowed_values=["Mean", "Median", "BiWeight", "ClippedMedian"]
			),
			'bkgboxpix': Option(
				name='bkgboxpix', 
				description='Assume box size option expressed in pixels (default: multiple of beam size)',
				category='IMGBKG',
				default_value=False
			), 
			'bkgbox' : ValueOption(
				name='bkgbox',
				value='',
				value_type=float, 
				description='Box size (multiple of beam size) used to compute local bkg',
				category='IMGBKG',
				default_value=20,
				min_value=0.01,
				max_value=1000.
			),
			'bkggrid' : ValueOption(
				name='bkggrid',
				value='',
				value_type=float, 
				description='Grid size (fraction of bkg box) used to compute local bkg',
				category='IMGBKG',
				default_value=0.2,
				min_value=0.,
				max_value=1.
			),
			'no-bkg2ndpass' : Option(
				name='no-bkg2ndpass', 
				description='Do not perform a 2nd pass in bkg estimation',
				category='IMGBKG',
				advanced=True,
				default_value=False
			),
			'bkgskipoutliers' : Option(
				name='bkgskipoutliers', 
				description='Remove bkg outliers (blobs above seed thr) when estimating bkg',
				category='IMGBKG',
				advanced=True,
				default_value=False
			),
			'sourcebkgboxborder' : ValueOption(
				name='sourcebkgboxborder',
				value='',
				value_type=int, 
				description='Border size (in pixels) of box around source used to estimate bkg for fitting',
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
				category='COMPACT-SOURCES',
				default_value=False
			),
			'npixmin' : ValueOption(
				name='npixmin',
				value='',
				value_type=int, 
				description='Minimum number of pixel to form a compact source',
				category='COMPACT-SOURCES',
				default_value=5,
				min_value=0,
				max_value=10000
			),
			'seedthr' : ValueOption(
				name='seedthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used in flood-fill algo',
				category='COMPACT-SOURCES',
				default_value=5,
				min_value=0,
				max_value=10000
			),
			'mergethr' : ValueOption(
				name='mergethr',
				value='',
				value_type=float, 
				description='Merge threshold (in nsigmas) used in flood-fill algo',
				category='COMPACT-SOURCES',
				default_value=2.5,
				min_value=0,
				max_value=10000
			),
			'compactsearchiters' : ValueOption(
				name='compactsearchiters',
				value='',
				value_type=int, 
				description='Maximum number of compact source search iterations. Increase this to detect more fainter sources at the cost of also detecting false sources or artefacts.',
				category='COMPACT-SOURCES',
				default_value=2,
				min_value=0,
				max_value=100
			),
			'seedthrstep' : ValueOption(
				name='seedthrstep',
				value='',
				value_type=float, 
				description='Seed thr decrease step across iterations',
				category='COMPACT-SOURCES',
				default_value=0.5,
				min_value=0,
				max_value=10
			),
	
			# == COMPACT SOURCE SELECTION OPTIONS ==
			'selectsources' : Option(
				name='selectsources', 
				description='Apply selection to compact sources found. Set to true if interested in detecting point-like sources.',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=False
			),
			'no-boundingboxcut' : Option(
				name='no-boundingboxcut', 
				description='If selectsources is enabled, do not apply bounding box cut',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=False
			),
			'minboundingbox' : ValueOption(
				name='minboundingbox',
				value='',
				value_type=int, 
				description='Minimum bounding box cut in pixels (NB: source tagged as bad if below this threshold)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=2,
				min_value=0,
				max_value=1000000
			),
			'no-circratiocut' : Option(
				name='no-circratiocut', 
				description='If selectsources is enabled, do not apply circular ratio parameter cut',	
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=False
			),
			'circratiothr' : ValueOption(
				name='circratiothr',
				value='',
				value_type=float, 
				description='Circular ratio threshold (0=line, 1=circle) (source passes point-like cut if above this threshold)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',	
				advanced=True,
				default_value=0.4,
				min_value=0.,
				max_value=1.
			),
			'no-elongationcut' : Option(
				name='no-elongationcut', 
				description='If selectsources is enabled, do not apply elongation parameter cut',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=False
			),
			'elongationthr' : ValueOption(
				name='elongationthr',
				value='',
				value_type=float, 
				description='Elongation threshold (source passes point-like cut if below this threshold',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=0.7,
				min_value=0.,
				max_value=1.
			),
			'ellipsearearatiocut' : Option(
				name='ellipsearearatiocut', 
				description='If selectsources is enabled, apply ellipse area ratio parameter cut',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=False
			),
			'ellipsearearatiominthr' : ValueOption(
				name='ellipsearearatiominthr',
				value='',
				value_type=float, 
				description='Ellipse area ratio min threshold',
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
				description='Ellipse area ratio max threshold',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				advanced=True,
				default_value=1.4,
				min_value=0.,
				max_value=10.
			),
			'maxnpixcut' : Option(
				name='maxnpixcut', 
				description='If selectsources is enabled, apply max pixels cut (NB: source below this thr passes the point-like cut)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=False
			),
			'maxnpix' : ValueOption(
				name='maxnpix',
				value='',
				value_type=int, 
				description='Max number of pixels for point-like sources (source passes point-like cut if below this threshold)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=1000,
				min_value=0.,
				max_value=10000000
			),
			'no-nbeamscut' : Option(
				name='no-nbeamscut', 
				description='If selectsources is enabled, do not apply the cut on the number of beams contained in a source',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=False
			),
			'nbeamsthr' : ValueOption(
				name='nbeamsthr',
				value='',
				value_type=float, 
				description='nBeams threshold (sources passes point-like cut if nBeams<thr)',
				category='COMPACT-SOURCES',
				subcategory='SELECTION',
				default_value=10,
				min_value=0.,
				max_value=1000.
			),


			# == COMPACT NESTED SOURCE OPTIONS ==
			'no-nestedsearch' : Option(
				name='no-nestedsearch', 
				description='Do not search for sources nested inside the sources previously extracted with the iterative flood-fill detection method.',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=True
			),
			'blobmaskmethod' : EnumValueOption(
				name='blobmaskmethod',
				value='',
				value_type=str, 
				description='Blob mask computation method',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value='MultiScaleLoG',
				allowed_values=['GausLaplacian', 'MultiScaleLoG']
			),

			'nested-sourcetobeamthr' : ValueOption(
				name='nested-sourcetobeamthr',
				value='',
				value_type=float, 
				description='Source area/beam thr to add nested sources (e.g. npix>thr*beamArea). NB: thr=0 means always if searchNestedSources is enabled',
				category='COMPACT-SOURCES',
				subcategory='NESTED-SOURCES',
				default_value=10.,
				min_value=0.,
				max_value=1000000.
			),
			'nested-blobthr' : ValueOption(
				name='nested-blobthr',
				value='',
				value_type=float, 
				description='Threshold (multiple of curvature median) used for nested blob finding',
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
				description='Minimum distance in pixels (in x or y) between nested and parent blob below which nested is skipped',
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
				description='Maximum fraction of matching pixels between nested and parent blob above which nested is skipped',
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
				description='Nested blob peak significance threshold (in scale curv map)',
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
				description='Nested blob significance merge threshold (in scale curv map)',
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
				description='Nested blob min scale search factor f (blob sigma_min=f x beam width)',
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
				description='Nested blob max scale search factor f (blob sigma_max=f x beam width)',
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
				description='Nested blob scale step (sigma=sigma_min + step)',
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
				description='Nested blob curvature/LoG kernel size factor f (kern size=f x sigma)',
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
				description='Fit compact point-like sources found. Enable this option for measuring compact source parameters (flux, position, extension).',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-usethreads' : Option(
				name='fit-usethreads', 
				description='Enable multithread in source fitting (NB: use Minuit2 minimizer if enabled)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=True # False previously
			),
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
			'fit-minimizeralgo' : EnumValueOption(
				name='fit-minimizeralgo',
				value='',
				value_type=str, 
				description='Fit minimizer algorithm',
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
				description='Fit print level',
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
				description='Fit strategy. Higher means more fit function calls (slower) but a more accurate minimum search',
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
				description='Maximum number of beams for fitting if compact source',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=100,
				min_value=0,
				max_value=100000
			),
			'fit-maxcomponents' : ValueOption(
				name='fit-maxcomponents',
				value='',
				value_type=int, 
				description='Maximum number of components fitted in a blob. Reduce it to limit spurious components when fitting diffuse/extended sources.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=3,
				min_value=0,
				max_value=100
			),
			'fit-usenestedascomponents' : Option(
				name='fit-usenestedascomponents', 
				description='Initialize fit components to nested sources found in source',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-freebkg' : Option(
				name='fit-freebkg', 
				description='Fit with bkg offset parameter free to vary',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-estimatedbkg' : Option(
				name='fit-estimatedbkg', 
				description='Set bkg par starting value to the estimated bkg (average over source pixels by default, box around source if --fit-usebkgboxestimate is given)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=True # previously set to False
			),
			'fit-usebkgboxestimate' : Option(
				name='fit-usebkgboxestimate', 
				description='Set bkg par starting value to the estimated bkg in a box around source',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-bkg' : ValueOption(
				name='fit-bkg',
				value='',
				value_type=float, 
				description='Bkg par starting value (NB: ineffective when --fit-estimatedbkg is enabled)',
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
				description='Limit amplitude range par (Speak*(1+-FIT_AMPL_LIMIT))',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=0.5,
				min_value=0.,
				max_value=2.
			),
			'prefit-freeampl' : Option(
				name='prefit-freeampl', 	
				description='Set amplitude as free par in pre-fit. If false, keep it fixed.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-sigmalimit' : ValueOption(
				name='fit-sigmalimit',
				value='',
				value_type=float, 
				description='Gaussian sigma limit around psf or beam (Bmaj*(1+-FIT_SIGMA_LIMIT))',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=0.5,
				min_value=0.,
				max_value=2.
			),
			'fit-thetalimit' : ValueOption(
				name='fit-thetalimit',
				value='',
				value_type=float, 
				description='Gaussian theta limit around psf or beam in degrees (e.g. Bpa +- FIT_THETA_LIMIT)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=360.,
				min_value=0.,
				max_value=360.
			),
			'fit-nobkglimits' : Option(
				name='fit-nobkglimits', 
				description='Do not apply limits in bkg offset parameter in fit',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-noampllimits' : Option(
				name='fit-noampllimits', 
				description='Do not apply limits in Gaussian amplitude parameters in fit',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-nosigmalimits' : Option(
				name='fit-nosigmalimits', 
				description='Do not apply limits in Gaussian sigma parameters in fit',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-noposlimits' : Option(
				name='fit-noposlimits', 
				description='Do not apply limits in Gaussian mean parameters in fit',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-poslimit' : ValueOption(
				name='fit-poslimit',
				value='',
				value_type=int, 
				description='Source centroid limits in pixel',	
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=3,
				min_value=0,
				max_value=1000
			),
			'prefit-freepos' : Option(
				name='prefit-freepos', 
				description='Set centroid as a free par in pre-fit. If False, keep it fixed.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-nothetalimits' : Option(
				name='fit-nothetalimits', 
				description='Do not apply limits in Gaussian ellipse pos angle parameters in fit',
				category='COMPACT-SOURCES',
				subcategory='FITTING'
			),
			'fit-fixsigma' : Option(
				name='fit-fixsigma',
				description='Fit with sigma parameters fixed to start value (beam bmaj/bmin) (default: fit with sigma free and constrained)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'prefit-fixsigma' : Option(
				name='prefit-fixsigma', 
				description='Fix sigma parameters in pre-fit. If False, keep them free.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-fixtheta' : Option(
				name='fit-fixtheta', 
				description='Fit with theta parameters fixed to start value (beam bpa) (default: fit with theta free and constrained)',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'prefit-fixtheta' : Option(
				name='prefit-fixtheta', 
				description='Fix theta parameter in pre-fit. If False, keep it free.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-peakminkern' : ValueOption(
				name='fit-peakminkern',
				value='',
				value_type=int, 
				description='Minimum dilation kernel size (in pixels) used to detect peaks',
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
				description='Maximum dilation kernel size (in pixels) used to detect peaks',
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
				description='Requested peak multiplicity across different dilation kernels (-1=peak found in all given kernels,1=only in one kernel, etc)',
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
				description='Shift tolerance (in pixels) used to compare peaks in different dilation kernels',
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
				description='Minimum peak flux significance (in nsigmas above avg source bkg & noise) below which peak is skipped',
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
				description='Fit function tolerance for convergence',
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
				description='Maximum number of fit iterations or function calls performed',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=1000000,
				min_value=0,
				max_value=1000000
			),
			'fit-noimproveconvergence' : Option(
				name='fit-noimproveconvergence', 
				description='Do not use iterative fitting to try to achieve fit convergence',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-noretry' : Option(
				name='fit-noretry', 
				description='Do not iteratively retry fit with less components in case of failed convergence',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-nretries' : ValueOption(
				name='fit-nretries',
				value='',
				value_type=int, 
				description='Maximum number of fit retries if fit failed or has parameters at bound',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=100,
				min_value=0,
				max_value=100000
			),
			'fit-parboundincreasestep' : ValueOption(
				name='fit-parboundincreasestep',
				value='',
				value_type=float, 
				description='Fit par bound increase step size (e.g. parmax= parmax_old+(1+nretry)*fitParBoundIncreaseStepSize*0.5*|max-min|). Used in iterative fitting',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=0.1,
				min_value=0.,
				max_value=10.
			),
			'fit-improveerrors' : Option(
				name='fit-improveerrors', 
				description='Run final minimizer step (e.g. HESS) to improve fit error estimates',
				category='COMPACT-SOURCES',
				subcategory='FITTING',	
				advanced=True,
				default_value=False
			),
			'fit-scaledatatomax' : Option(
				name='fit-scaledatatomax', 
				description='Scale source data to max pixel flux for fitting. Otherwise scale to mJy.',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),
			'fit-nochi2cut' : Option(
				name='fit-nochi2cut', 
				description='Do not apply reduced chi2 cut to fitted sources',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=False
			),
			'fit-chi2cut' : ValueOption(
				name='fit-chi2cut',
				value='',
				value_type=float, 
				description='Chi2 cut value',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				default_value=5.,
				min_value=0.,
				max_value=1000.
			),
			'fit-useellipsecuts' : Option(
				name='fit-useellipsecuts', 
				description='Apply ellipse cuts to fitted sources',
				category='COMPACT-SOURCES',
				subcategory='FITTING',
				advanced=True,
				default_value=False
			),

			# == SOURCE RESIDUAL OPTIONS ==
			'computeresiduals' : Option(
				name='computeresiduals', 
				description='Compute compact source residual map (after compact source search)',
				category='IMGRES',
				default_value=False
			),
			'res-removenested' : Option(
				name='res-removenested', 
				description='When a source has nested sources, perform the source removal only on nested sources',
				category='IMGRES',
				default_value=False
			),
			'res-zthr' : ValueOption(
				name='res-zthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used to dilate sources',
				category='IMGRES',
				default_value=5.,
				min_value=0.,
				max_value=10000.
			),
			'res-zhighthr' : ValueOption(
				name='res-zhighthr',
				value='',
				value_type=float, 
				description='Seed threshold (in nsigmas) used to dilate sources (even if they have nested components or different dilation type)',
				category='IMGRES',
				default_value=10.,
				min_value=0.,
				max_value=10000.
			),
			'dilatekernsize' : ValueOption(
				name='dilatekernsize',
				value='',
				value_type=int, 
				description='Size of dilating kernel in pixels',
				category='IMGRES',
				default_value=9,
				min_value=1,
				max_value=1001
			),
			'res-removedsourcetype' : EnumValueOption(
				name='res-removedsourcetype',
				value='',
				value_type=str, 
				description='Type of source dilated from the input image',
				category='IMGRES',
				default_value='POINT-LIKE',
				allowed_values=['ALL','COMPACT','POINT-LIKE','EXTENDED']
			),
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
				category='IMGRES',
				default_value=False
			),

			# == SMOOTHING FILTER OPTIONS ==
			'no-presmoothing' : Option(	
				name='no-presmoothing', 
				description='Do not smooth input/residual map before extended source search',
				category='IMGSMOOTH',
				default_value=False
			),
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
				description='Guided filter radius par',
				category='IMGSMOOTH',
				default_value=12.,
				min_value=0.,
				max_value=1000.
			),
			'guidedfilter-eps' : ValueOption(
				name='guidedfilter-eps',
				value='',
				value_type=float, 
				description='Guided filter eps par',
				category='IMGSMOOTH',
				default_value=0.04,
				min_value=0.,
				max_value=1000.
			),

			# == EXTENDED SOURCE SEARCH OPTIONS ==
			'no-extendedsearch' : Option(
				name='no-extendedsearch', 
				description='Do not search extended sources. If True, extended sources are searched with --extsfinder selected method',
				category='EXTENDED-SOURCES',
				default_value=False
			),
			'extsfinder' : EnumValueOption(
				name='extsfinder',
				value='',
				value_type=str, 
				description='Extended source search method',	
				category='EXTENDED-SOURCES',
				default_value='SALIENCY-THRESH',
				allowed_values=['WT-THRESH','SP-HIERCLUST','ACTIVE-CONTOUR','SALIENCY-THRESH']
			),
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
				description='Superpixel size (in pixels) used in hierarchical clustering',
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
				description='Superpixel regularization par (beta) used in hierarchical clustering',
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
				description='Superpixel min area (in pixels) used in hierarchical clustering',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=10,
				min_value=1,
				max_value=10000
			),
			'saliency-nooptimalthr' : Option(
				name='saliency-nooptimalthr', 	
				description='Do not use optimal threshold in multiscale saliency estimation (e.g. use median thr)',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY'
			),
			'saliency-thr' : ValueOption(
				name='saliency-thr',
				value='',
				value_type=float, 
				description='Saliency map threshold factor wrt optimal/median threshold',
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
				description='Superpixel size (in pixels) used in multi-reso saliency map smallest scale',
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
				description='Superpixel size (in pixels) used in multi-reso saliency map highest scale',
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
				description='Superpixel size step (in pixels) used in multi-reso saliency map computation',
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
				description='Fraction of most similar region neighbors used in saliency map computation',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True,
				default_value=1.,
				min_value=0,
				max_value=1.
			),
			'saliency-usebkgmap' : Option(
				name='saliency-usebkgmap', 
				description='Use bkg map in saliency computation',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True,
				default_value=False
			),
			'saliency-usermsmap' : Option(
				name='saliency-usermsmap', 
				description='Use noise map in saliency computation',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				advanced=True,
				default_value=False
			),
			'saliency-userobustpars' : Option(
				name='saliency-userobustpars', 
				description='Use robust pars in saliency computation',
				category='EXTENDED-SOURCES',
				subcategory='SALIENCY',
				default_value=False
			),

			# == ACTIVE-CONTOUR MAIN OPTIONS ==
			'ac-niters' : ValueOption(
				name='ac-niters',	
				value='',
				value_type=int, 
				description='Maximum number of iterations in active-contour algorithms',
				category='EXTENDED-SOURCES',
				subcategory='ACTIVE-CONTOUR',
				default_value=1000,
				min_value=1,
				max_value=100000
			),
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
				description='Init level set size par (f x image size) in active-contour algorithms',
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
				description='Tolerance par in active-contour algorithms',
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
				description='Maximum number of inner iterations in ChanVese algorithm',
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
				description='Maximum number of re-init iterations in ChanVese algorithm',
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
				description='Chan-Vese time step parameter',
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
				description='Chan-Vese algo window size parameter',
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
				description='Chan-Vese algo lambda1 parameter',
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
				description='Chan-Vese algo lambda2 parameter',
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
				description='Chan-Vese algo mu parameter',
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
				description='Chan-Vese algo nu parameter',
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
				description='Chan-Vese algo p parameter',
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
				description='Minimum Wavelet Transform scale for extended source search',
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
				description='Maximum Wavelet Transform scale for extended source search',
				category='EXTENDED-SOURCES',
				subcategory='WAVELET-TRANSFORM',
				default_value=6,
				min_value=1,
				max_value=10
			),

			# == RUN OPTIONS ==
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
				description='Do not redirect logs to output file in script. If True, no log file produced and returned as output product (only internal Slurm log)',
				category='RUN',
				default_value=False
			),
			'no-mpi' : Option(
				name='no-mpi', 
				description='Disable MPI run. If False, MPI is used (even with 1 proc).',
				category='RUN',
				default_value=True
			),
			'nproc' : ValueOption(
				name='nproc',
				value='',
				value_type=int, 
				description='Number of MPI processors per node used (NB: mpi tot nproc=nproc x nnodes)',
				category='RUN',
				default_value=1,
				min_value=1,
				max_value=1000
			),
			'nthreads' : ValueOption(
				name='nthreads',
				value='',
				value_type=int, 
				description='Number of threads to be used in OpenMP (-1=all available in node)',
				category='RUN',
				default_value=1,
				min_value=-1,
				max_value=1000
			),
			
			# == SFINDER SUBMISSION OPTIONS ==
			# --> NOT EXPOSED THROUGH THE API
			
			# == PARALLEL PROCESSING OPTIONS ==
			'tilesplit' : Option(
				name='tilesplit', 
				description='Partition input image in tiles and perform distributed processing (default=no tile split)',
				category='RUN',
				default_value=False
			),
			'tilesize' : ValueOption(
				name='tilesize',
				value='',
				value_type=int, 
				description='Size (in pixels) of tile used to partition input image in distributed processing (0=no tile split)', 
				category='RUN',
				default_value=0.,
				min_value=0.,
				max_value=10000000.
			),
			'tilestep' : ValueOption(
				name='tilestep',
				value='',
				value_type=float, 
				description='Tile step size (range 0-1) expressed as tile fraction used in tile overlap (1=no overlap)',
				category='RUN',
				default_value=1.,
				min_value=0.001,
				max_value=1.
			),
			'mergeedgesources' : Option(
				name='mergeedgesources', 
				description='Merge sources at tile edges. NB: Used for multitile processing',
				category='RUN',
				default_value=True
			),
			'no-mergesources' : Option(
				name='no-mergesources', 
				description='If True, disable source merging in each tile',
				category='RUN',
				default_value=True
			),


		} # close dict

		# - Define dictionary with job outputs produced
		self.job_outputs= {
		
		}

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
		self.cmd_args.append("--save-catalog-to-json ")



	
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
		
