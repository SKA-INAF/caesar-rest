
# - BROKER OPTIONS
####broker_url= 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
####broker_url= 'redis://localhost:6379'
broker_url= 'amqp://guest:guest@localhost:5672/' # correct one
broker_heartbeat=0

# - RESULT BACKEND OPTIONS	
####result_backend= 'rpc://'
####result_backend= 'redis://localhost:6379'
result_backend = 'redis://localhost:6379/0' # correct one
####result_backend = 'mongodb://localhost:27017/caesardb'

# - BEAT SCHEDULE OPTIONS
beat_schedule = {
	'accounter_beat': {
  	'task': 'caesar_rest.accounter.accounter_task',
  	'schedule': 120.0,
	},
	'job_monitoring_beat': {
  	'task': 'caesar_rest.job_monitor.jobmonitor_task',
  	'schedule': 30.0,
	},
}


# - OTHER TASK OPTIONS
imports = ('caesar_rest.workers','caesar_rest.accounter','caesar_rest.job_monitor')
accept_content = ['json', 'application/text']
result_accept_content = ['json']
task_serializer = 'json'
result_serializer = 'json'
timezone = "UTC"
task_time_limit = 86400 # 24 h
task_soft_time_limit = 18000 # 5h



