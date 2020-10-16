##############################
#   MODULE IMPORTS
##############################
from functools import wraps
from flask import current_app, request, g
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
			if g.oidc_id_token is None:
				logger.info("Calling OIDC login ...")
				#return oidc.require_login(func(*args, **kwargs))
				#return oidc.require_login(func)
				#return oidc.redirect_to_auth_server(func, request.values)
				return oidc.redirect_to_auth_server(request.url)
			else:
				return func(*args, **kwargs)
		else:		
			return func(*args, **kwargs)

	return decorated
