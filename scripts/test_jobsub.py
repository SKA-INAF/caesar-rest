from __future__ import print_function

############################################################
#              MODULE IMPORTS
############################################################
# - Standard modules
import os
import sys
import json
import time
import datetime
import numpy as np
import argparse
import logging

import asyncio
import aiohttp
import requests
import csv

logging.basicConfig(format="%(asctime)-15s %(levelname)s - %(message)s",datefmt='%Y-%m-%d %H:%M:%S')
logger= logging.getLogger(__name__)
logger.setLevel(logging.INFO)

###########################
##     ARGS
###########################
def get_args():
	"""This function parses and return arguments passed in"""
	parser = argparse.ArgumentParser(description="Parse args.")

	# - Specify cmd options
	parser.add_argument('-fileid','--fileid', dest='fileid', required=True, type=str, help='File id to be used for job submission') 
	parser.add_argument('-njobs','--njobs', dest='njobs', default=1, required=False, type=int, help='Number of jobs to be submitted')
	parser.add_argument('-service_host','--service_host', dest='service_host', required=True, type=str, help='Service host or ipaddress')
	parser.add_argument('-service_port','--service_port', dest='service_port', required=True, type=str, help='Service port')
	parser.add_argument('-outputfile','--outputfile', dest='outputfile', default='jobstats.csv', required=False, type=str, help='Output csv file with job stats')
	parser.add_argument('-sleep_time','--sleep_time', dest='sleep_time', default=10, required=False, type=int, help='Sleep time after each job monitoring')
	

	args = parser.parse_args()	

	return args


###########################
##     SUBMIT JOB
###########################
async def submit_job(session, url, data, headers):
	""" Submit job """

	
	t0= time.perf_counter()
	try:
		print("data")
		print(data)

		async with session.post(url, data=data, headers=headers) as response:
			resp= await response.text()
			#resp= await response.read()
			
			t1= time.perf_counter()
			time_taken  = t1 - t0 
			logger.info("Job submission reply")
			print(resp)
			response.raise_for_status()

			print("URL : ", url)
			print("HTTP Status : ", response.status)
			print(f"Time taken : {time_taken:4f} seconds")
			print()
			#return str(response.url), response.status, time_taken
			#return str(resp), response.status, time_taken
			return resp, response.status, time_taken

	except Exception as e:
		logger.warn("Failed to send request (err=%s)" % str(e))


async def submit_jobs(njobs, url, data, headers):
	
	""" Submit a job to service """
	
	async with aiohttp.ClientSession() as session:
		    
		# - Prepare the coroutines that post
		logger.info("Preparing the post requests ...")
		post_tasks = []
		#async for i in range(0,njobs):
		for i in range(0,njobs):
			post_tasks.append(submit_job(session, url, data, headers))
        
		# - Now execute them all at once
		logger.info("Executing the post requests ...")
		ret= await asyncio.gather(*post_tasks)

	logger.info("Finalized all job submissions. Return is a list of len {} outputs.".format(len(ret)))

	return ret



###########################
##     MAIN
###########################
def main():
	""" Main function """

	#===========================
	#==   PARSE ARGS
	#===========================
	logger.info("Parsing cmd line arguments ...")
	try:
		args= get_args()
	except Exception as ex:
		logger.error("Failed to get and parse options (err=%s)",str(ex))
		sys.exit(1)

	fileid= args.fileid
	host= args.service_host
	port= args.service_port
	njobs= args.njobs	
	outputfile= args.outputfile	
	sleep_time= args.sleep_time

	url= ''.join("http://%s:%s/caesar/api/v1.0/job" % (host,port))

	#===========================
	#==   SET JOB DATA
	#===========================
	data_dict= {"app": "caesar", "tag": "stresstest", "data_inputs": fileid, "job_inputs": {"no-mpi": True,"no-logredir": True, "no-extendedsearch": True, "fitsources": True}}
	#data= {"app": "caesar", "tag": "stresstest", "data_inputs": fileid}
	
	data= json.dumps(data_dict)

	headers = {
    'Content-Type': 'application/json'
	}

	#===========================
	#==   RUN SUBMISSION
	#===========================
	loop = asyncio.get_event_loop ()
	start = time.time()
	ret= loop.run_until_complete(submit_jobs(njobs, url, data, headers))
	end = time.time()
	elapsed= end - start

	logger.info("Took {} seconds to complete the job submission".format(elapsed))

	print("ret")
	print(ret)

	#===========================
	#==   MONITOR JOBS
	#===========================
	
	# - Find list of jobs to be monitored
	njobs_submitted= 0
	#job_data_list= []
	job_ids= []
	job_submit_times= []

	for job_info in ret:
		if job_info is None:
			logger.warn("Job data is None, skip to next...")
			continue

		job_data= json.loads(job_info[0])
		job_submit_status= job_info[1]
		job_submit_time= job_info[2]
		job_submit_times.append(job_submit_time)

		if job_submit_status!=202:
			logger.warn("Job failed to be submitted (status=%d)" % job_submit_status)
			continue

		njobs_submitted+= 1
		job_id= job_data["job_id"]
		job_state= job_data["state"]
		job_ids.append(job_id)
		#job_data_list.append({"job_id": job_id, "state": job_state})
		
	logger.info("Submitted %d jobs with success" % njobs_submitted)
	print("--> job ids")
	print(job_ids)

	job_submit_time_min= np.min(job_submit_times)
	job_submit_time_max= np.max(job_submit_times)
	job_submit_time_mean= np.mean(job_submit_times)
	job_submit_time_median= np.median(job_submit_times)
	job_submit_time_sigma= np.std(job_submit_times)
	job_submit_time_mad= np.median(np.absolute(job_submit_times - job_submit_time_median))


	# - Monitor jobs
	timeout= 10
	jobs_completed= False
	job_status_data_list= []
	for i in range(len(job_ids)):
		job_status_data_list.append({})
	
	try:
		
		while not jobs_completed:

			# - Loop over jobs and monitor
			for i in range(len(job_ids)):
				job_id= job_ids[i]
				logger.info("Monitoring job %s ..." % job_id)
				
				query_url= ''.join("http://%s:%s/caesar/api/v1.0/job/%s/status" % (host,port,job_id))
				try:
					reply= requests.get(
						query_url, 
						headers=headers,
						timeout= timeout 
					)

					jobout= json.loads(reply.text)

					print("--> jobout")
					print(jobout)
					
					job_status_data_list[i]= jobout

				except requests.Timeout:
					logger.warn("Failed to query job status to url %s (err=request timeout)" % url)
					continue

				except requests.ConnectionError:
					logger.warn("Failed to query job status to url %s (err=connection error)" % url)
					continue

				except Exception as e:
					logger.warn("Failed to query job status to url %s (err=%s)" % (url,str(e)))
					continue


			# - Check if jobs completed
			nsuccess= 0
			nfailed= 0
			npending= 0
			nrunning= 0
			jobs_completed= True

			for job_status_data in job_status_data_list:
				if not job_status_data or job_status_data is None: 
					logger.warn("Job status data is empty, possibly was not retrieved from the server...try again later...")
					break
				job_id= job_status_data["job_id"]
				job_state= job_status_data["state"]
				exit_code= job_status_data["exit_code"]

				if job_state=="SUCCESS":
					if exit_code==0:
						nsuccess+= 1
					else:
						logger.warn("Job %s marked as SUCCESS but exit code !=0, counting as failed..." % job_id)
						nfailed+= 1
				if job_state=="PENDING":
					npending+= 1
					jobs_completed= False
				if job_state=="RUNNING":
					nrunning+= 1
					jobs_completed= False
				if job_state=="FAILURE":
					nfailed+= 1

			logger.info("Job monitoring stats: ntot=%d, nsubmitted=%d, nsuccess=%d, nfailed=%s, nrunning=%d, npending=%d" % (njobs, njobs_submitted, nsuccess, nfailed, nrunning, npending))

			if jobs_completed:
				logger.info("All jobs completed, stop monitoring...")
				break

			# - Sleeping a bit before monitoring again
			logger.info("Sleeping %s seconds ..." % sleep_time)
			time.sleep(sleep_time)
						
	except KeyboardInterrupt:
		logger.info("Job monitoring interrupted with ctrl-c signal")
		return -1	

		
	# - Compute some stats
	elapsed_times= []

	for job_status_data in job_status_data_list:
		if not job_status_data or job_status_data is None: 
			continue
		job_state= job_status_data["state"]
		elapsed_time= job_status_data["elapsed_time"]
		exit_code= job_status_data["exit_code"]
		success= (job_state=='SUCCESS' and exit_code==0)
		if not success:
			continue

		elapsed_times.append(elapsed_time)	

	elapsed_time_min= np.min(elapsed_times)
	elapsed_time_max= np.max(elapsed_times)
	elapsed_time_mean= np.mean(elapsed_times)
	elapsed_time_sigma= np.std(elapsed_times)
	elapsed_time_median= np.median(elapsed_times)
	elapsed_time_mad= np.median(np.absolute(elapsed_times - elapsed_time_median))

	logger.info("elapsed time stats: mean=%f, median=%f, stddev=%f, mad=%f" % (elapsed_time_mean,elapsed_time_median,elapsed_time_sigma,elapsed_time_mad))


	# - Write stats to file
	with open(outputfile, mode='w') as fout:
		writer = csv.writer(fout, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
		writer.writerow([
			'#njobs', 
			'nsubmitted', 
			'nsuccess', 
			'nfailed', 
			't_min', 
			't_max', 
			't_mean', 
			't_median', 
			't_std', 
			't_mad',
			'tsub_min',
			'tsub_max',
 			'tsub_mean',
			'tsub_median',
			'tsub_sigma',
			'tsub_mad',
		])
		writer.writerow([
			njobs, 
			njobs_submitted, 
			nsuccess, 
			nfailed, 
			elapsed_time_min, 
			elapsed_time_max, 
			elapsed_time_mean, 
			elapsed_time_median, 
			elapsed_time_sigma, 
			elapsed_time_mad,
			job_submit_time_min,
			job_submit_time_max,
			job_submit_time_mean,
			job_submit_time_median,
			job_submit_time_sigma,
			job_submit_time_mad
		])

	return 0


###################
##   MAIN EXEC   ##
###################
if __name__ == "__main__":
	main()


