##############################
#   MODULE IMPORTS
##############################
from flask import current_app, Blueprint, render_template, request, redirect
from caesar_rest import oidc

##############################
#   CREATE BLUEPRINT
##############################
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
	if oidc.user_loggedin:
		return render_template('index.html', username=oidc.user_getfield('email'))
        	#return 'Welcome {email}'.format(email=oidc.user_getfield('email'))
    	else:
        	return 'Not logged in, <a href="/login">Log in</a> '


@index_bp.route('/login')
@oidc.require_login
def login():
    user_info = oidc.user_getinfo(['preferred_username', 'email', 'sub', 'name'])
    # return value is a dictionary with keys the above keywords
    return redirect("/", code=302) #'Welcome {user_info}'.format(user_info=user_info['name'])


@index_bp.route('/logout')
def logout():
    """Performs local logout by removing the session cookie."""

    oidc.logout()
    return 'Hi, you have been logged out! <a href="/">Return</a>'
