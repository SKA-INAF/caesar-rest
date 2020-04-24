#! /usr/bin/env python

# - Celery options (do not change variable names)
#broker_url= 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
broker_url= 'amqp://guest:guest@localhost:5672/'

###broker_url= 'redis://localhost:6379'
broker_heartbeat=0
	
#result_backend= 'rpc://'
###result_backend= 'redis://localhost:6379'
result_backend = 'redis://localhost:6379/0'

imports = ('caesar_rest.workers',)

accept_content = ['json', 'application/text']
result_accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = "UTC"

task_time_limit = 86400 # 24 h
task_soft_time_limit = 18000 # 5h


