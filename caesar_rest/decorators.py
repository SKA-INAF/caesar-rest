##############################
#   MODULE IMPORTS
##############################
from functools import wraps
from flask import current_app, request
from caesar_rest import oidc

# Get logger
import logging
logger = logging.getLogger(__name__)

def custom_require_login(func):
	""" Decorator to require login only if AAI is enabled """

	@wraps(func)
	def decorated(*args, **kwargs):
		aai_enabled= current_app.config['USE_AAI']
		has_oidc= (oidc is not None)
		logger.info("use_aai? %d has_oidc? %d" % (aai_enabled, has_oidc))

		if aai_enabled and has_oidc:
			logger.info("Calling OIDC login ...")
			#return oidc.require_login(func)
			return oidc.redirect_to_auth_server(func, request.values)
			#logger.info("After OIDC login ...")
		else:		
			return func(*args, **kwargs)

		#logger.info("Calling original func ...")
		#func()

	return decorated
