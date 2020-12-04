#! /usr/bin/env python

__title__ = 'caesar_rest'
__version__ = '1.0.0'
__author__ = 'Simone Riggi'
__license__ = 'GPL3'
__date__ = '2020-04-17'
__copyright__ = 'Copyright 2020 by Simone Riggi - INAF'


import logging
import logging.config

# Create the Logger
logging.basicConfig(format="%(asctime)-15s %(levelname)s - %(message)s",datefmt='%Y-%m-%d %H:%M:%S')
logger= logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.info("This is caesar_rest {0}-({1})".format(__version__, __date__))

# Create celery
from celery import Celery
celery= Celery(
	__name__,
	config_source='caesar_rest.celery_config'
)

# Create OIDC (without connecting to app)
oidc= None
try:
	from flask_oidc_ex import OpenIDConnect
	oidc = OpenIDConnect()

except:
	logger.warn("flask_oidc module not found, can't create OpenIDConnect(), no AAI will be used (hint: install flask_oidc)")

# Create MongoDB engine
mongo= None
try:
	from flask_pymongo import PyMongo
	mongo= PyMongo()

except Exception as e:
	errmsg= 'flask_pymongo module not found or failed to create mongo instance (err=' + str(e) + ')'
	logger.error(errmsg)
	raise ImportError(errmsg)

