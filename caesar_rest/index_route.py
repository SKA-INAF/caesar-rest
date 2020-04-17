##############################
#   MODULE IMPORTS
##############################
from flask import current_app, Blueprint, render_template, request, redirect


##############################
#   CREATE BLUEPRINT
##############################
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
	return render_template('index.html')
