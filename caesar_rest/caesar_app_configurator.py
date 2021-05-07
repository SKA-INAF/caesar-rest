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
from caesar_rest.base_app_configurator import Option, ValueOption

# Get logger
logger = logging.getLogger(__name__)



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
			'inputfile' : ValueOption('inputfile','',str,True),
			#'filelist' : ValueOption('filelist','',True),
		
			# == OUTPUT OPTIONS ==
			'save-fits' : Option('save-fits', description='Save maps (if save enabled) in FITS format (default=ROOT format)'),
			'save-inputmap' : Option('save-inputmap', description='Save input map in output ROOT file (default=no)'),
			'save-bkgmap' : Option('save-bkgmap', description='Save bkg map in output ROOT file (default=no)'),
			'save-rmsmap' : Option('save-rmsmap', description='Save rms map in output ROOT file (default=no)'),
			'save-significancemap' : Option('save-significancemap', description='Save significance map in output ROOT file (default=no)'),
			'save-residualmap' : Option('save-residualmap', description='Save residual map in output ROOT file (default=no)'),
			'save-saliencymap' : Option('save-saliencymap', description='Save saliency map in output ROOT file (default=no)'),
			'save-segmentedmap' : Option('save-segmentedmap', description='Save segmented map in output ROOT file (default=no)'),
			'save-regions' : Option('save-regions', description='Save DS9 regions (default=no)'),
			'convertregionstowcs' : Option('convertregionstowcs', description='Save DS9 regions in WCS format (default=no)'),
			'regionwcs' : ValueOption('regionwcs','',int, description='DS9 region WCS output format (0=J2000,1=B1950,2=GALACTIC) (default=0)'),

			# == IMG READ OPTIONS ==
			'tilesize' : ValueOption('tilesize','',int, description='Size (in pixels) of tile used to partition input image in distributed processing (default=0=no tile split)'),
			'tilestep' : ValueOption('tilestep','',float, description='Tile step size (range 0-1) expressed as tile fraction used in tile overlap (default=1=no overlap)'),
			'xmin' : ValueOption('xmin','',int, description='Read sub-image of input image starting from pixel x=xmin (default=0=read full image)'),
			'xmax' : ValueOption('xmax','',int, description='Read sub-image of input image up to pixel x=xmax (default=0=read full image)'),
			'ymin' : ValueOption('ymin','',int, description='Read sub-image of input image starting from pixel y=xmin (default=0=read full image)'),
			'ymax' : ValueOption('ymax','',int, description='Read sub-image of input image up to pixel y=ymax (default=0=read full image)'),

			# == STATS OPTIONS ==		
			'no-parallelmedian' : Option('no-parallelmedian', description='Switch off parallel median algorithm (based on parallel nth-element)'),

			# == BKG OPTIONS ==		
			'bmaj' : ValueOption('bmaj','',float, description='User-supplied beam Bmaj in arcsec (NB: used only when beam info is not available in input map) (default: 10 arcsec)'),
			'bmin' : ValueOption('bmin','',float, description='User-supplied beam Bmin in arcsec (NB: used only when beam info is not available in input map) (default: 5 arcsec)'),
			'bpa' : ValueOption('bpa','',float, description='User-supplied beam position angle in degrees (NB: used only when beam info is not available in input map) (default: 0 deg)'),
			'mappixsize' : ValueOption('mappixsize','',float, description='Map pixel size in arcsec (NB: used only when info is not available in input map) (default=1 arcsec)'),
			'globalbkg' : Option('globalbkg', description='Use global bkg (default=use local bkg)'),
			'bkgestimator' : ValueOption('bkgestimator','',int, description='Stat estimator used for bkg (1=Mean,2=Median,3=BiWeight,4=ClippedMedian) (default=2)'),
			'bkgboxpix': Option('bkgboxpix', description='Consider box size option expressed in pixels and not as a multiple of beam size (default=no)'), 
			'bkgbox' : ValueOption('bkgbox','',int, description='Box size (muliple of beam size) used to compute local bkg (default=20 x beam)'),
			'bkggrid' : ValueOption('bkggrid','',float, description='Grid size (fraction of bkg box) used to compute local bkg (default=0.2 x box)'),
			'no-bkg2ndpass' : Option('no-bkg2ndpass', description='Do not perform a 2nd pass in bkg estimation (default=true)'),
			'bkgskipoutliers' : Option('bkgskipoutliers', description='Remove bkg outliers (blobs above seed thr) when estimating bkg (default=no)'),
			'sourcebkgboxborder' : ValueOption('sourcebkgboxborder','',int, description='Border size (in pixels) of box around source bounding box used to estimate bkg for fitting (default=20)'),

			# == SFINDER OPTIONS ==		
			'mergeedgesources' : Option('mergeedgesources', description='Merge sources at tile edges. NB: Used for multitile processing. (default=no)'),
			'no-mergesources' : Option('no-mergesources', description='Disable source merging in each tile (default=enabled)'),
			#'no-mergecompactsources' : Option('no-mergecompactsources'),
			#'no-mergeextsources' : Option('no-mergeextsources'),

			# == COMPACT SOURCE SEARCH OPTIONS ==
			'no-compactsearch' : Option('no-compactsearch', description='Do not search compact sources'),
			'npixmin' : ValueOption('npixmin','',int, description='Minimum number of pixel to form a compact source (default=5 pixels)'),
			'seedthr' : ValueOption('seedthr','',float, description='Seed threshold (in nsigmas) used in flood-fill (default=5 sigmas)'),
			'mergethr' : ValueOption('mergethr','',float, description='Merge threshold (in nsigmas) used in flood-fill (default=2.6 sigmas)'),
			'compactsearchiters' : ValueOption('compactsearchiters','',int, description='Maximum number of compact source search iterations (default=1)'),
			'seedthrstep' : ValueOption('seedthrstep','',float, description='Seed thr decrease step across iterations (default=0.5)'),
	
			# == COMPACT SOURCE SELECTION OPTIONS ==
			'selectsources' : Option('selectsources', description='Apply selection to compact sources found (default=false)'),
			'no-boundingboxcut' : Option('no-boundingboxcut', description='Do not apply bounding box cut (default=apply)'),
			'minboundingbox' : ValueOption('minboundingbox','',int, description='Minimum bounding box cut in pixels (NB: source tagged as bad if below this threshold) (default=2)'),
			'no-circratiocut' : Option('no-circratiocut', description='Do not apply circular ratio parameter cut (default=apply)'),
			'circratiothr' : ValueOption('circratiothr','',float, description='Circular ratio threshold (0=line, 1=circle) (source passes point-like cut if above this threshold) (default=0.4)'),
			'no-elongationcut' : Option('no-elongationcut', description='Do not apply elongation parameter cut (default=apply)'),
			'elongationthr' : ValueOption('elongationthr','',float, description='Elongation threshold (source passes point-like cut if below this threshold (default=0.7)'),
			'ellipsearearatiocut' : Option('ellipsearearatiocut', description='Apply ellipse area ratio parameter cut (default=not applied)'),
			'ellipsearearatiominthr' : ValueOption('ellipsearearatiominthr','',float, description='Ellipse area ratio min threshold (default=0.6)'),
			'ellipsearearatiomaxthr' : ValueOption('ellipsearearatiomaxthr','',float, description='Ellipse area ratio max threshold (default=1.4)'),
			'maxnpixcut' : Option('maxnpixcut', description='Apply max pixels cut (NB: source below this thr passes the point-like cut) (default=not applied)'),
			'maxnpix' : ValueOption('maxnpix','',int, description='Max number of pixels for point-like sources (source passes point-like cut if below this threshold) (default=1000)'),
			'no-nbeamscut' : Option('no-nbeamscut', description='Use number of beams in source cut (default=applied)'),
			'nbeamsthr' : ValueOption('nbeamsthr','',float, description='nBeams threshold (sources passes point-like cut if nBeams<thr) (default=3)'),


			# == COMPACT NESTED SOURCE OPTIONS ==
			'no-nestedsearch' : Option('no-nestedsearch', description='Do not search nested sources (default=search)'),
			'blobmaskmethod' : ValueOption('blobmaskmethod','',int, description='Blob mask method (1=gaus smooth+Laplacian,2=multi-scale LoG) (default=2)'),
			'nested-sourcetobeamthr' : ValueOption('nested-sourcetobeamthr','',float, description='Source area/beam thr to add nested sources (e.g. npix>thr*beamArea). NB: thr=0 means always if searchNestedSources is enabled (default=5)'),
			'nested-blobthr' : ValueOption('nested-blobthr','',float, description='Threshold (multiple of curvature median) used for nested blob finding (default=0)'),
			'nested-minmotherdist' : ValueOption('nested-minmotherdist','',int, description='Minimum distance in pixels (in x or y) between nested and parent blob below which nested is skipped (default=2)'),
			'nested-maxmotherpixmatch' : ValueOption('nested-maxmotherpixmatch','',float, description='Maximum fraction of matching pixels between nested and parent blob above which nested is skipped (default=0.5)'),
			'nested-blobpeakzthr' : ValueOption('nested-blobpeakzthr','',float, description='Nested blob peak significance threshold (in scale curv map) (default=5)'),
			'nested-blobpeakzthrmerge' : ValueOption('nested-blobpeakzthrmerge','',float, description='Nested blob significance merge threshold (in scale curv map) (default=2.5)'),
			'nested-blobminscale' : ValueOption('nested-blobminscale','',float, description='Nested blob min scale search factor f (blob sigma_min=f x beam width) (default=1)'),
			'nested-blobmaxscale' : ValueOption('nested-blobmaxscale','',float, description='Nested blob max scale search factor f (blob sigma_max=f x beam width) (default=3)'),
			'nested-blobscalestep' : ValueOption('nested-blobscalestep','',float, description='Nested blob scale step (sigma=sigma_min + step) (default=1)'),
			'nested-blobkernfactor' : ValueOption('nested-blobkernfactor','',float, description='Nested blob curvature/LoG kernel size factor f (kern size=f x sigma) (default=1)'),

			# == EXTENDED SOURCE SEARCH OPTIONS ==
			'no-extendedsearch' : Option('no-extendedsearch', description='Do not search extended sources'),
			'extsfinder' : ValueOption('extsfinder','',int, description='Extended source search method {1=WT-thresholding,2=SPSegmentation,3=ActiveContour,4=Saliency thresholding} (default=3)'),
			'activecontour' : ValueOption('activecontour','',int, description='Active contour method {1=Chanvese, 2=LRAC} (default=2)'),
			
			# == SOURCE RESIDUAL OPTIONS ==
			'computeresiduals' : Option('computeresiduals', description='Compute compact source residual map (after compact source search)'),
			'res-removenested' : Option('res-removenested', description='When a source has nested sources remove only on nested (default=false)'),
			'res-zthr' : ValueOption('res-zthr','',float, description='Seed threshold (in nsigmas) used to dilate sources (default=5 sigmas)'),
			'res-zhighthr' : ValueOption('res-zhighthr','',float, description='Seed threshold (in nsigmas) used to dilate sources (even if they have nested components or different dilation type) (default=10 sigmas)'),
			'dilatekernsize' : ValueOption('dilatekernsize','',int, description='Size of dilating kernel in pixels (default=9)'),
			'res-removedsourcetype' : ValueOption('res-removedsourcetype','',int, description='Type of source dilated from the input image (-1=ALL,1=COMPACT,2=POINT-LIKE,3=EXTENDED) (default=2)'),
			'res-pssubtractionmethod' : ValueOption('res-pssubtractionmethod','',int, description='Method used to subtract point-sources in residual map (1=DILATION, 2=FIT MODEL REMOVAL)'),
			'res-bkgaroundsource': Option('res-bkgaroundsource', description='Usebkg computed around source rather than the one computed using the global/local bkg map (default=false)'),

			# == SOURCE FITTING OPTIONS ==
			'fitsources' : Option('fitsources', description='Fit compact point-like sources found (default=false)'),
			'fit-usethreads' : Option('fit-usethreads', description='Enable multithread in source fitting (NB: use Minuit2 minimizer if enabled) (default=disabled)'),
			'fit-minimizer' : ValueOption('fit-minimizer','',str, description='Fit minimizer {Minuit,Minuit2} (default=Minuit2)'),
			'fit-minimizeralgo' : ValueOption('fit-minimizeralgo','',str, description='Fit minimizer algo {migrad,simplex,minimize,scan,fumili (Minuit2)} (default=minimize)'),
			'fit-printlevel' : ValueOption('fit-printlevel','',int, description='Fit print level (default=1)'),
			'fit-strategy' : ValueOption('fit-strategy','',int, description='Fit strategy (default=2)'),
			'fit-maxnbeams' : ValueOption('fit-maxnbeams','',int, description='Maximum number of beams for fitting if compact source (default=20)'),
			'fit-maxcomponents' : ValueOption('fit-maxcomponents','',int, description='Maximum number of components fitted in a blob (default=3)'),
			'fit-usenestedascomponents' : Option('fit-usenestedascomponents', description='Initialize fit components to nested sources found in source (default=no)'),
			'fit-freebkg' : Option('fit-freebkg', description='Fit with bkg offset parameter free to vary (default=fixed)'),
			'fit-estimatedbkg' : Option('fit-estimatedbkg', description='Set bkg par starting value to estimated bkg (average over source pixels by default, box around source if --fit-estimatedboxbkg is given) (default=use fixed bkg start value)'),
			'fit-usebkgboxestimate' : Option('fit-usebkgboxestimate', description='Set bkg par starting value to estimated bkg (from box around source)'),
			'fit-bkg' : ValueOption('fit-bkg','',float, description='Bkg par starting value (NB: ineffective when -fit-estimatedbkg is enabled) (default=0)'),
			'fit-ampllimit' : ValueOption('fit-ampllimit','',float, description='Limit amplitude range par (Speak*(1+-FIT_AMPL_LIMIT)) (default=0.3)'),
			'prefit-freeampl' : Option('prefit-freeampl', description='Set free amplitude par in pre-fit (default=fixed)'),
			'fit-sigmalimit' : ValueOption('fit-sigmalimit','',float, description='Gaussian sigma limit around psf or beam (Bmaj*(1+-FIT_SIGMA_LIMIT)) (default=0.3)'),
			'fit-thetalimit' : ValueOption('fit-thetalimit','',float, description='Gaussian theta limit around psf or beam in degrees (e.g. Bpa +- FIT_THETA_LIMIT) (default=90)'),
			'fit-nobkglimits' : Option('fit-nobkglimits', description='Do not apply limits in bkg offset parameter in fit (default=fit with limits when par is free)'),
			'fit-noampllimits' : Option('fit-noampllimits', description='Do not apply limits in Gaussian amplitude parameters in fit (default=fit with limits)'),
			'fit-nosigmalimits' : Option('fit-nosigmalimits', description='Do not apply limits in Gaussian sigma parameters in fit (default=fit with limits)'),
			'fit-noposlimits' : Option('fit-noposlimits', description='Do not apply limits in Gaussian mean parameters in fit (default=fit with limits)'),
			'fit-poslimit' : ValueOption('fit-poslimit','',int, description='Source centroid limits in pixel (default=3)'),
			'prefit-freepos' : Option('prefit-freepos', description='Set free centroid pars in pre-fit (default=fixed)'),
			'fit-nothetalimits' : Option('fit-nothetalimits', description='Do not apply limits in Gaussian ellipse pos angle parameters in fit (default=fit with limits)'),
			'fit-fixsigma' : Option('fit-fixsigma', description='Fit with sigma parameters fixed to start value (beam bmaj/bmin) (default=fit with sigma free and constrained)'),
			'prefit-fixsigma' : Option('prefit-fixsigma', description='Fix sigma parameters in pre-fit (default=free)'),
			'fit-fixtheta' : Option('fit-fixtheta', description='Fit with theta parameters fixed to start value (beam bpa) (default=fit with theta free and constrained)'),
			'prefit-fixtheta' : Option('prefit-fixtheta', description='Fix theta parameter in pre-fit (default=free)'),
			'fit-peakminkern' : ValueOption('fit-peakminkern','',int, description='Minimum dilation kernel size (in pixels) used to detect peaks (default=3)'),
			'fit-peakmaxkern' : ValueOption('fit-peakmaxkern','',int, description='Maximum dilation kernel size (in pixels) used to detect peaks (default=7)'),
			'fit-peakmultiplicitythr' : ValueOption('fit-peakmultiplicitythr','',int, description='Requested peak multiplicity across different dilation kernels (-1=peak found in all given kernels,1=only in one kernel, etc) (default=1)'),
			'fit-peakshifttol' : ValueOption('fit-peakshifttol','',int, description='Shift tolerance (in pixels) used to compare peaks in different dilation kernels (default=2 pixels)'),
			'fit-peakzthrmin' : ValueOption('fit-peakzthrmin','',float, description='Minimum peak flux significance (in nsigmas above avg source bkg & noise) below which peak is skipped (default=1)'),
			'fit-fcntol' : ValueOption('fit-fcntol','',float, description='Fit function tolerance for convergence (default 1.e-2)'),
			'fit-maxniters' : ValueOption('fit-maxniters','',int, description='Maximum number of fit iterations or function calls performed (default 10000)'),
			'fit-noimproveconvergence' : Option('fit-noimproveconvergence', description='Do not use iterative fitting to try to achieve fit convergence (default=use)'),
			'fit-noretry' : Option('fit-noretry', description='Do not iteratively retry fit with less components in case of failed convergence (default=retry)'),
			'fit-nretries' : ValueOption('fit-nretries','',int, description='Maximum number of fit retries if fit failed or has parameters at bound (default 10)'),
			'fit-parboundincreasestep' : ValueOption('fit-parboundincreasestep','',float, description='Fit par bound increase step size (e.g. parmax= parmax_old+(1+nretry)*fitParBoundIncreaseStepSize*0.5*|max-min|). Used in iterative fitting. (default=0.1)'),
			'fit-improveerrors' : Option('fit-improveerrors', description='Run final minimizer step (e.g. HESS) to improve fit error estimates (default=no)'),
			'fit-scaledatatomax' : Option('fit-scaledatatomax', description='Scale source data to max pixel flux for fitting. Otherwise scale to mJy (default=no)'),
			'fit-nochi2cut' : Option('fit-nochi2cut', description='Do not apply reduced chi2 cut to fitted sources (default=apply)'),
			'fit-chi2cut' : ValueOption('fit-chi2cut','',float, description='Chi2 cut value (default=5)'),
			'fit-useellipsecuts' : Option('fit-useellipsecuts', description='Apply ellipse cuts to fitted sources (default=not applied)'),

			# == SMOOTHING FILTER OPTIONS ==
			'no-presmoothing' : Option('no-presmoothing', description='Do not smooth input/residual map before extended source search (default=yes)'),
			'smoothfilter' : ValueOption('smoothfilter','',int, description='Smoothing filter to be used (1=gaussian, 2=guided filter) (default=2)'),
			'guidedfilter-radius' : ValueOption('guidedfilter-radius','',float, description='Guided filter radius par (default=12)'),
			'guidedfilter-eps' : ValueOption('guidedfilter-eps','',float, description='Guided filter eps par (default=0.04)'),

			# == SALIENCY FILTER OPTIONS ==
			'sp-size' : ValueOption('sp-size','',int, description='Superpixel size (in pixels) used in hierarchical clustering (default=20)'),
			'sp-beta' : ValueOption('sp-beta','',float, description='Superpixel regularization par (beta) used in hierarchical clustering (default=1)'),
			'sp-minarea' : ValueOption('sp-minarea','',int, description='Superpixel min area (in pixels) used in hierarchical clustering (default=10)'),
			'saliency-nooptimalthr' : Option('saliency-nooptimalthr', description='Do not use optimal threshold in multiscale saliency estimation (e.g. use median thr) (default=use optimal)'),
			'saliency-thr' : ValueOption('saliency-thr','',float, description='Saliency map threshold factor wrt optimal/median threshold (default=2.8)'),
			'saliency-minreso' : ValueOption('saliency-minreso','',int, description='Superpixel size (in pixels) used in multi-reso saliency map smallest scale (default=20 pixels)'),
			'saliency-maxreso' : ValueOption('saliency-maxreso','',int, description='Superpixel size (in pixels) used in multi-reso saliency map highest scale (default=60 pixels)'),
			'saliency-resostep' : ValueOption('saliency-resostep','',int, description='Superpixel size step (in pixels) used in multi-reso saliency map computation (default=10 pixels)'),
			'saliency-nn' : ValueOption('saliency-nn','',float, description='Fraction of most similar region neighbors used in saliency map computation (default=1)'),
			'saliency-usebkgmap' : Option('saliency-usebkgmap', description='Use bkg map in saliency computation (default=not used)'),
			'saliency-usermsmap' : Option('saliency-usermsmap', description='Use noise map in saliency computation (default=not used)'),
			'saliency-userobustpars' : Option('saliency-userobustpars', description='Use robust pars in saliency computation (default=no)'),

			# == ACTIVE-CONTOUR MAIN OPTIONS ==
			'ac-niters' : ValueOption('ac-niters','',int, description='Maximum number of iterations in active-contour algorithms (default=1000)'),
			'ac-levelset' : ValueOption('ac-levelset','',int, description='Init level set method in active-contour algorithms (1=circle,2=checkerboard,3=saliency) (default=1)'),
			'ac-levelsetsize' : ValueOption('ac-levelsetsize','',float, description='Init level set size par in active-contour algorithms (default=0.1ximage size)'),
			'ac-tolerance' : ValueOption('ac-tolerance','',float, description='Tolerance par in active-contour algorithms (default=0.1)'),

			# == CHAN-VESE OPTIONS ==
			'cv-nitersinner' : ValueOption('cv-nitersinner','',int, description='Maximum number of inner iterations in ChanVese algorithm (default=1000)'),
			'cv-nitersreinit' : ValueOption('cv-nitersreinit','',int, description='Maximum number of re-init iterations in ChanVese algorithm (default=1000)'),
			'cv-timestep' : ValueOption('cv-timestep','',float, description='Chan-Vese time step parameter (default=0.007)'),
			'cv-wsize' : ValueOption('cv-wsize','',float, description='Chan-Vese window size parameter (default=1)'),
			'cv-lambda1' : ValueOption('cv-lambda1','',float, description='Chan-Vese lambda1 parameter (default=1)'),
			'cv-lambda2' : ValueOption('cv-lambda2','',float, description='Chan-Vese lambda2 parameter (default=2)'),
			'cv-mu' : ValueOption('cv-mu','',float, description='Chan-Vese mu parameter (default=0.5)'),
			'cv-nu' : ValueOption('cv-nu','',float, description='Chan-Vese nu parameter (default=0)'),
			'cv-p' : ValueOption('cv-p','',float, description='Chan-Vese p parameter (default=1)'),

			# == WAVELET TRANSFORM FILTER OPTIONS ==
			'wtscalemin' : ValueOption('wtscalemin','',int, description='Minimum Wavelet Transform scale for extended source search (default=3)'),
			'wtscalemax' : ValueOption('wtscalemax','',int, description='Maximum Wavelet Transform scale for extended source search (default=6)'),

			# == RUN OPTIONS ==
			'run' : Option('run', description='Run the generated run script on the local shell. If disabled only run script will be generated for later run'),
			'envfile' : ValueOption('envfile','',str, description='File (.sh) with list of environment variables to be loaded by each processing node'),
			'loglevel' : ValueOption('loglevel','',str, description='Logging level string {INFO, DEBUG, WARN, ERROR, OFF} (default=INFO)'),
			'maxfiles' : ValueOption('maxfiles','',int, description='Maximum number of input files processed in filelist (default=-1=all files)'),
			'addrunindex' : Option('addrunindex', description='Append a run index to submission script (in case of list execution) (default=no)'),
			'jobdir' : ValueOption('jobdir','',str, description='Job directory where to run (default=pwd)'),			
			'outdir' : ValueOption('outdir','',str, description='Output directory where to put run output file (default=pwd)'),
			'no-logredir' : Option('no-logredir', description='Do not redirect logs to output file in script'),
			'no-mpi' : Option('no-mpi', description='Disable MPI run (even with 1 proc) (default=enabled)'),
			'mpioptions' : ValueOption('mpioptions','',str, description='Options to be passed to MPI (e.g. --bind-to {none,hwthread, core, l1cache, l2cache, l3cache, socket, numa, board}) (default=none)'),
			'nproc' : ValueOption('nproc','',int, description='Number of MPI processors per node used (NB: mpi tot nproc=nproc x nnodes) (default=1)'),
			'nthreads' : ValueOption('nthreads','',int, description='Number of threads to be used in OpenMP (default=-1=all available in node)'),
			'hostfile' : ValueOption('hostfile','',str, description='Ascii file with list of hosts used by MPI (default=no hostfile used)'),
			'containerrun' : Option('containerrun', description='Run inside Caesar container'),
			'containerimg' : ValueOption('containerimg','',str, description='Singularity container image file (.simg) with CAESAR installed software'),
			'containeroptions' : ValueOption('containeroptions','',str, description='Options to be passed to container run (e.g. -B /home/user:/home/user) (default=none)'),

			# == SFINDER SUBMISSION OPTIONS ==
			'submit' : Option('submit', description='Submit the script to the batch system using queue specified. Takes precedence over local run.'),
			'batchsystem' : ValueOption('batchsystem','',str, description='Name of batch system. Valid choices are {PBS,SLURM} (default=PBS)'),
			'queue' : ValueOption('queue','',str, description='Name of queue in batch system'),
			'jobwalltime' : ValueOption('jobwalltime','',str, description='Job wall time in batch system (default=96:00:00)'),
			'jobcpus' : ValueOption('jobcpus','',int, description='Number of cpu per node requested for the job (default=1)'),
			'jobnodes' : ValueOption('jobnodes','',int, description='Number of nodes requested for the job (default=1)'),
			'jobmemory' : ValueOption('jobmemory','',float, description='Memory in GB required for the job (default=4)'),
			'jobusergroup' : ValueOption('jobusergroup','',str, description='Name of job user group batch system (default=empty)'),

		} # close dict

		# - Define option value transformers
		self.option_value_transformer= {
			'inputfile': self.transform_inputfile
		}

		# - Fill some default cmd args
		use_slurm= current_app.config['USE_SLURM']
		if use_slurm:
			logger.info("Adding Slurm options by default ...")
			queue_opt= '--queue=' + current_app.config['SLURM_QUEUE']
			self.cmd_args.append("--batchsystem=SLURM")
			self.cmd_args.append(queue_opt)
		else:
			logger.info("Adding --run option by default ...")
			self.cmd_args.append("--run")

	

	def transform_inputfile(self,file_uuid):
		""" Transform input file from uuid to actual path """		
	
		# - Get aai info
		username= 'anonymous'
		if ('oidc_token_info' in g) and (g.oidc_token_info is not None and 'email' in g.oidc_token_info):
			email= g.oidc_token_info['email']
			username= utils.sanitize_username(email)

		# - Inspect inputfile (expect it is a uuid, so convert to filename)
		logger.info("Finding inputfile uuid %s ..." % file_uuid)
		collection_name= username + '.files'

		file_path= ''
		try:
			data_collection= mongo.db[collection_name]
			item= data_collection.find_one({'fileid': str(file_uuid)})
			if item and item is not None:
				file_path= item['filepath']
			else:
				logger.warn("File with uuid=%s not found in DB!" % file_uuid)
				file_path= ''
		except Exception as e:
			logger.error("Exception (err=%s) catch when searching file in DB!" % str(e))
			return ''
		
		if not file_path or file_path=='':
			logger.warn("inputfile uuid %s is empty or not found in the system!" % file_uuid)
			return ''

		logger.info("inputfile uuid %s converted in %s ..." % (file_uuid,file_path))

		return file_path
		
