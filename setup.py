#! /usr/bin/env python
"""
Setup for caesar-rest
"""
import os
import sys
from setuptools import setup, find_packages


def read(fname):
	"""Read a file"""
	return open(os.path.join(os.path.dirname(__file__), fname)).read()


def get_version():
	""" Get the package version number """
	import caesar_rest
	return caesar_rest.__version__



PY_MAJOR_VERSION=sys.version_info.major
PY_MINOR_VERSION=sys.version_info.minor
print("PY VERSION: maj=%s, min=%s" % (PY_MAJOR_VERSION,PY_MINOR_VERSION))

reqs= []
reqs.append('numpy>=1.10')

if PY_MAJOR_VERSION<=2:
	print("PYTHON 2 detected")
	reqs.append('future')
	
else:
	print("PYTHON 3 detected")
	reqs.append('MarkupSafe==1.1') # There is syntax error in pre-release version 2.0.0a for python3
	
reqs.append('werkzeug>=1.0')
#reqs.append('requests')
reqs.append('flask')
	

data_dir = 'data'

setup(
	name="caesar_rest",
	#package="caesar_rest",
	version=get_version(),
	author="Simone Riggi",
	author_email="simone.riggi@gmail.com",
	description="Rest API for Caesar source finder application",
	license = "GPL3",
	url="https://github.com/SKA-INAF/caesar-rest",
	long_description=read('README.md'),
	#packages=['caesar_rest'],
	packages=find_packages(),
	include_package_data=True,
	zip_safe=False,
	install_requires=reqs,
	scripts=['apps/run_app.py'],
)
