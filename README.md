# caesar-rest
caesar-rest provides a rest interface for caesar [https://github.com/SKA-INAF/caesar] source finder and related applications based on Flask python framework [https://palletsprojects.com/p/flask/]. Celery task queue is used to execute caesar application jobs asynchronously. In this application Celery is configured by default to use a RabbitMQ broker for message exchange and Redis as task result store. In a production environment caesar rest service can be run behind nginx+uwsgi http server. 

## **Status**
This software is under development. Not already tested with python 3.

## **Credit**
This software is distributed with GPLv3 license. If you use caesar-rest for your research, please add repository link or acknowledge authors in your papers.   

## **Installation**  

### **Install dependencies**
To run caesar rest service you need to install the following tools:  

* rabbitmq [https://www.rabbitmq.com/]    
* redis [https://redis.io/]  
* celery [http://www.celeryproject.org/] 
* uwsgi [https://uwsgi-docs.readthedocs.io/en/latest/index.html]   
* nginx [https://nginx.org/]      

### **Package installation**
To build and install the package:    

* Create a local install directory, e.g. ```$INSTALL_DIR```
* Add installation path to your ```PYTHONPATH``` environment variable:   
  ``` export PYTHONPATH=$PYTHONPATH:$INSTALL_DIR/lib/python2.7/site-packages ```
* Build and install package:   
  ``` python setup.py sdist bdist_wheel```    
  ``` python setup build```   
  ``` python setup install --prefix=$INSTALL_DIR```   

All dependencies will be automatically downloaded and installed in ```$INSTALL_DIR```.   
     
To use package scripts:

* Add binary directory to your ```PATH``` environment variable:   
  ``` export PATH=$PATH:$INSTALL_DIR/bin ```    

## **How to run?**  

### **Preliminary setup**
Before running the application you must do some preparatory stuff:   

* Create the application working dir (by default `/opt/caesar-rest`)   
* Create the top directory for data upload (by default `/opt/caesar-rest/data`)   
* Create the top directory for jobs (by default `/opt/caesar-rest/jobs`)   
* (OPTIONAL) Create the log directory for system services (see below), e.g. `/opt/caesar-rest/logs` 
* (OPTIONAL) Create the run directory for system services (see below), e.g. `/opt/caesar-rest/run` 
* (OPTIONAL) Create a dedicated user & group (e.g. `caesar`) allowed to run the application and services and give it ownership of the directories previously created     

### **Run backend services**
To run caesar-rest you must first run the message broker, the task store and worker services:

* Run rabbitmq message broker service:  
   ```systemctl start rabbitmq-server.service```   
* Run redis store service:    
   ```systemctl start redis.service```   
* Run celery worker with desired concurrency level (e.g. 2):  
   ```celery -A caesar_rest worker --loglevel=INFO --concurrency=2```   
   
   In production you may want to run this as a system service:   
       
   - Create a `/etc/default/caesar-workers` configuration file (e.g. see the example in the `config/celery` directory):  
   
     ```
     # The names of the workers. Only one here. 
     CELERYD_NODES="caesar_worker"    
     
     # The name of the Celery App   
     CELERY_APP="caesar_rest"
      
     # Working dir    
     CELERYD_CHDIR="/opt/caesar-rest"    
     
     # Additional options    
     CELERYD_OPTS="--time-limit=300 --concurrency=4"

     # Log and PID directories    
     CELERYD_LOG_FILE="/opt/caesar-rest/logs/%n%I.log"    
     CELERYD_PID_FILE="/opt/caesar-rest/run/%n.pid"    

     # Log level    
     CELERYD_LOG_LEVEL=INFO    

     # Path to celery binary, that is in your virtual environment    
     CELERY_BIN=/usr/local/bin/celery    
     ```
     
   - Create a `/etc/systemd/system/caesar-workers.service` systemd service file:    
   
     ```
     [Unit]    
     Description=Caesar Celery Worker Service    
     After=network.target rabbitmq-server.target redis.target   

     [Service]    
     Type=forking   
     User=caesar   
     Group=caesar   
     EnvironmentFile=/etc/default/caesar-workers     
     Environment="PATH=$INSTALL_DIR/bin"   
     Environment="PYTHONPATH=$INSTALL_DIR/lib/python2.7/site-packages"   
     WorkingDirectory=/opt/caesar-rest   
     ExecStart=/bin/sh -c '${CELERY_BIN} multi start ${CELERYD_NODES} \    
       -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} \   
       --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'    
     ExecStop=/bin/sh -c '${CELERY_BIN} multi stopwait ${CELERYD_NODES} \    
       --pidfile=${CELERYD_PID_FILE}'   
     ExecReload=/bin/sh -c '${CELERY_BIN} multi restart ${CELERYD_NODES} \   
       -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} \   
       --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'    

     [Install]    
     WantedBy=multi-user.target   
     ```
  
  - Start the service:   
     ```sudo systemctl caesar-workers.service start```    
   
### **Run the application in development mode**   
To run caesar-rest in development mode, e.g. for debug or testing purposes:   

  ```$INSTALL_DIR/bin/run_app.py --[ARGS]```

where supported `ARGS` are:    

   * `datadir=[DATADIR]`: Directory where to store uploaded data (default: /opt/caesar-rest/data)   
   * `jobdir=[JOBDIR]`: Top directory where to store job data (default: /opt/caesar-rest/data)
   * `debug`: Run Flask application in debug mode if given   
   
Flask default options are defined in the `config.py`. Celery options are defined in the `celery_config.py`. Other options may be defined in the future to override default Flask and Celery options.   

### **Run the application in production**   
In a production environment you can run the application behind a nginx+uwsgi (or nginx+gunicorn) server. In the `config` directory of the repository you can find sample files to create and configure required services. For example:  

* Start the application with uwsgi:   
     
  ```uwsgi --wsgi-file $INSTALL_DIR/bin/run_app.py --callable app [WSGI_CONFIG_FILE]```

  where `WSGI_CONFIG_FILE` is a configuration file (.ini format) for uwsgi. A sample configuration file is provided in the `config/uwgsi` directory:   
  
  ```
  [uwsgi]
  processes = 4   
  threads = 2   
  socket = ./run/caesar-rest.sock   
  ;socket = :5000
  ;http-socket = :5000
  socket-timeout = 65
  
  buffer-size = 32768  
  master = true   
  chmod-socket = 660   
  vacuum = true  
  die-on-term = true  
  ```
  
  In production you may want to run this as a system service: 
  
  - Create an `/etc/systemd/system/caesar-rest.service` systemd service file, for example following the example provided in the `config/uwsgi` directory:       
       
    ```
    [Unit]
    Description=uWSGI instance to serve caesar-rest application    
    After=network.target caesar-workers.target   

    [Service]
    User=caesar  
    Group=www-data   
    WorkingDirectory=/opt/caesar-rest  
    Environment="PATH=$INSTALL_DIR/bin"   
    Environment="PYTHONPATH=$INSTALL_DIR/lib/python2.7/site-packages"  
    ExecStart=/usr/bin/uwsgi --wsgi-file $INSTALL_DIR/bin/run_app.py --callable app --ini /opt/caesar-rest/config/uwsgi.ini

    [Install]   
    WantedBy=multi-user.target    
    ```   
    
   - Start the service:   
     ```sudo systemctl caesar-rest.service start```    

* Start the nginx service:

  - Create a `/etc/nginx/conf.d/nginx.conf` configuration file (see example file provided in the `config/nginx` directory):      
    ```
    server {   
      listen 8080;   
      client_max_body_size 1000M;   
      sendfile on;    
      keepalive_timeout 0;   
      location / {   
        include uwsgi_params;    
        #uwsgi_pass flask:5000;   
        uwsgi_pass unix:/opt/caesar-rest/run/caesar-rest.sock;   
      }       
    }    
    ```
  
    With this sample configuration the nginx server will listen at port 8080 and call the caesar-rest application via socket.    
   
  - Create a `/etc/systemd/system/nginx.service` systemd file, e.g. see the example provided in the `config/nginx` directory:   
  
    ```
    [Unit]   
    Description=The NGINX HTTP and reverse proxy server  
    After=syslog.target network.target remote-fs.target nss-lookup.target caesar-rest.target   

    [Service]   
    Type=forking    
    PIDFile=/run/nginx.pid   
    ExecStartPre=/usr/sbin/nginx -t   
    ExecStart=/usr/sbin/nginx   
    ExecReload=/usr/sbin/nginx -s reload   
    ExecStop=/bin/kill -s QUIT $MAINPID   
    PrivateTmp=true    

    [Install]   
    WantedBy=multi-user.target   
    ```
  
  - Run nginx server:   

    ```sudo systemctl start nginx```


## **Usage**  
caesar-rest provides the following REST endpoints:   

### **Data upload**

* URL:```http://server-address:port/caesar/api/v1.0/upload```   
* Request methods: POST   
* Request header: ```content-type: multipart/form-data```   

A sample curl request would be:   

```
curl -X POST \   
  -H 'Content-Type: multipart/form-data' \   
  -F 'file=@VGPS_cont_MOS017.fits' \   
  --url 'http://localhost:8080/caesar/api/v1.0/upload'   
```

Server response is:   
```
{
  "date":"2020-04-24T17:04:26.174333",
  "filename_orig":"VGPS_cont_MOS017.fits",
  "format":"fits",
  "path":"/opt/caesar-rest/data/250fdf5ed6a044888cf4406338f9e73b.fits",
  "size":4.00726318359375,
  "status":"File uploaded with success",
  "uuid":"250fdf5ed6a044888cf4406338f9e73b"
}
```

A file uuid (or file path) are returned and can be used to download the file or set job input file information.   

### **Data download**

* URL:```http://server-address:port/caesar/api/v1.0/download-id/[file_id]```   
* Request methods: GET, POST   
* Request header: None  

A sample curl request would be:   

```
curl  -X GET \
  --fail -o data.fits \
  --url 'http://localhost:8080/caesar/api/v1.0/download-id/67a49bf7555b41739095681bf52a1f99'
```

The above request will fail if file is not found, otherwise the downloaded file will be saves as `data.fits`. Without the `-o` argument raw output is written to stdout. If file is not found a json response is returned:   

```
{
  "status": "File with uuid 67a49bf7555b41739095681bf52a1f99 not found on the system!"
}
```

### **App description**
To get the list of supported apps:   

* URL:```http://server-address:port/caesar/api/v1.0/apps```   
* Request methods: GET   
* Request header: none

Server response contains a list of valid apps that can be queried for further description and used in job submission:    

```
{
  "apps": [
    "sfinder"
  ]
}
```

To get information about a given app:  

* URL:```http://server-address:port/caesar/api/v1.0/app/[app_name]/describe```   
* Request methods: GET    
* Request header: none

Server response contains a list of app options that can be used in job submission:   

```
{"ac-levelset":{"mandatory":false,"type":"int"},"ac-levelsetsize":{"mandatory":false,"type":"float"},"ac-niters":{"mandatory":false,"type":"int"},"ac-tolerance":{"mandatory":false,"type":"float"},"activecontour":{"mandatory":false,"type":"int"},"addrunindex":{"mandatory":false,"type":"none"},"batchsystem":{"mandatory":false,"type":"str"},"bkgbox":{"mandatory":false,"type":"int"},"bkgestimator":{"mandatory":false,"type":"int"},"bkggrid":{"mandatory":false,"type":"float"},"bkgskipoutliers":{"mandatory":false,"type":"none"},"blobmaskmethod":{"mandatory":false,"type":"int"},"bmaj":{"mandatory":false,"type":"float"},"bmin":{"mandatory":false,"type":"float"},"bpa":{"mandatory":false,"type":"float"},"circratiothr":{"mandatory":false,"type":"float"},"compactsearchiters":{"mandatory":false,"type":"int"},"computeresiduals":{"mandatory":false,"type":"none"},"containerimg":{"mandatory":false,"type":"str"},"containeroptions":{"mandatory":false,"type":"str"},"containerrun":{"mandatory":false,"type":"none"},"convertregionstowcs":{"mandatory":false,"type":"none"},"cv-lambda1":{"mandatory":false,"type":"float"},"cv-lambda2":{"mandatory":false,"type":"float"},"cv-mu":{"mandatory":false,"type":"float"},"cv-nitersinner":{"mandatory":false,"type":"int"},"cv-nitersreinit":{"mandatory":false,"type":"int"},"cv-nu":{"mandatory":false,"type":"float"},"cv-p":{"mandatory":false,"type":"float"},"cv-timestep":{"mandatory":false,"type":"float"},"cv-wsize":{"mandatory":false,"type":"float"},"dilatekernsize":{"mandatory":false,"type":"int"},"ellipsearearatiocut":{"mandatory":false,"type":"none"},"ellipsearearatiomaxthr":{"mandatory":false,"type":"float"},"ellipsearearatiominthr":{"mandatory":false,"type":"float"},"elongationthr":{"mandatory":false,"type":"float"},"envfile":{"mandatory":false,"type":"str"},"extsfinder":{"mandatory":false,"type":"int"},"fit-ampllimit":{"mandatory":false,"type":"float"},"fit-bkg":{"mandatory":false,"type":"float"},"fit-chi2cut":{"mandatory":false,"type":"float"},"fit-estimatedbkg":{"mandatory":false,"type":"none"},"fit-fcntol":{"mandatory":false,"type":"float"},"fit-fixsigma":{"mandatory":false,"type":"none"},"fit-fixtheta":{"mandatory":false,"type":"none"},"fit-freebkg":{"mandatory":false,"type":"none"},"fit-improveerrors":{"mandatory":false,"type":"none"},"fit-maxcomponents":{"mandatory":false,"type":"int"},"fit-maxnbeams":{"mandatory":false,"type":"int"},"fit-maxniters":{"mandatory":false,"type":"int"},"fit-minimizer":{"mandatory":false,"type":"str"},"fit-minimizeralgo":{"mandatory":false,"type":"str"},"fit-noampllimits":{"mandatory":false,"type":"none"},"fit-nobkglimits":{"mandatory":false,"type":"none"},"fit-nochi2cut":{"mandatory":false,"type":"none"},"fit-noimproveconvergence":{"mandatory":false,"type":"none"},"fit-noposlimits":{"mandatory":false,"type":"none"},"fit-noretry":{"mandatory":false,"type":"none"},"fit-nosigmalimits":{"mandatory":false,"type":"none"},"fit-nothetalimits":{"mandatory":false,"type":"none"},"fit-nretries":{"mandatory":false,"type":"int"},"fit-parboundincreasestep":{"mandatory":false,"type":"float"},"fit-peakmaxkern":{"mandatory":false,"type":"int"},"fit-peakminkern":{"mandatory":false,"type":"int"},"fit-peakmultiplicitythr":{"mandatory":false,"type":"int"},"fit-peakshifttol":{"mandatory":false,"type":"int"},"fit-peakzthrmin":{"mandatory":false,"type":"float"},"fit-poslimit":{"mandatory":false,"type":"int"},"fit-printlevel":{"mandatory":false,"type":"int"},"fit-scaledatatomax":{"mandatory":false,"type":"none"},"fit-sigmalimit":{"mandatory":false,"type":"float"},"fit-strategy":{"mandatory":false,"type":"int"},"fit-thetalimit":{"mandatory":false,"type":"float"},"fit-usebkgboxestimate":{"mandatory":false,"type":"none"},"fit-useellipsecuts":{"mandatory":false,"type":"none"},"fit-usenestedascomponents":{"mandatory":false,"type":"none"},"fit-usethreads":{"mandatory":false,"type":"none"},"fitsources":{"mandatory":false,"type":"none"},"globalbkg":{"mandatory":false,"type":"none"},"guidedfilter-eps":{"mandatory":false,"type":"float"},"guidedfilter-radius":{"mandatory":false,"type":"float"},"hostfile":{"mandatory":false,"type":"str"},"inputfile":{"mandatory":true,"type":"str"},"jobcpus":{"mandatory":false,"type":"int"},"jobmemory":{"mandatory":false,"type":"float"},"jobnodes":{"mandatory":false,"type":"int"},"jobusergroup":{"mandatory":false,"type":"str"},"jobwalltime":{"mandatory":false,"type":"str"},"loglevel":{"mandatory":false,"type":"str"},"mappixsize":{"mandatory":false,"type":"float"},"maxfiles":{"mandatory":false,"type":"int"},"maxnpix":{"mandatory":false,"type":"int"},"maxnpixcut":{"mandatory":false,"type":"none"},"mergeedgesources":{"mandatory":false,"type":"none"},"mergethr":{"mandatory":false,"type":"float"},"minboundingbox":{"mandatory":false,"type":"int"},"mpioptions":{"mandatory":false,"type":"str"},"nbeamsthr":{"mandatory":false,"type":"float"},"nested-blobkernfactor":{"mandatory":false,"type":"float"},"nested-blobmaxscale":{"mandatory":false,"type":"float"},"nested-blobminscale":{"mandatory":false,"type":"float"},"nested-blobpeakzthr":{"mandatory":false,"type":"float"},"nested-blobpeakzthrmerge":{"mandatory":false,"type":"float"},"nested-blobscalestep":{"mandatory":false,"type":"float"},"nested-blobthr":{"mandatory":false,"type":"float"},"nested-maxmotherpixmatch":{"mandatory":false,"type":"float"},"nested-minmotherdist":{"mandatory":false,"type":"int"},"nested-sourcetobeamthr":{"mandatory":false,"type":"float"},"no-bkg2ndpass":{"mandatory":false,"type":"none"},"no-boundingboxcut":{"mandatory":false,"type":"none"},"no-circratiocut":{"mandatory":false,"type":"none"},"no-compactsearch":{"mandatory":false,"type":"none"},"no-elongationcut":{"mandatory":false,"type":"none"},"no-extendedsearch":{"mandatory":false,"type":"none"},"no-logredir":{"mandatory":false,"type":"none"},"no-mergecompactsources":{"mandatory":false,"type":"none"},"no-mergeextsources":{"mandatory":false,"type":"none"},"no-mergesources":{"mandatory":false,"type":"none"},"no-mpi":{"mandatory":false,"type":"none"},"no-nbeamscut":{"mandatory":false,"type":"none"},"no-nestedsearch":{"mandatory":false,"type":"none"},"no-parallelmedian":{"mandatory":false,"type":"none"},"no-presmoothing":{"mandatory":false,"type":"none"},"npixmin":{"mandatory":false,"type":"int"},"nproc":{"mandatory":false,"type":"int"},"nthreads":{"mandatory":false,"type":"int"},"outdir":{"mandatory":false,"type":"str"},"prefit-fixsigma":{"mandatory":false,"type":"none"},"prefit-fixtheta":{"mandatory":false,"type":"none"},"prefit-freeampl":{"mandatory":false,"type":"none"},"prefit-freepos":{"mandatory":false,"type":"none"},"queue":{"mandatory":false,"type":"str"},"regionwcs":{"mandatory":false,"type":"int"},"res-pssubtractionmethod":{"mandatory":false,"type":"int"},"res-removedsourcetype":{"mandatory":false,"type":"int"},"res-removenested":{"mandatory":false,"type":"none"},"res-zhighthr":{"mandatory":false,"type":"float"},"res-zthr":{"mandatory":false,"type":"float"},"run":{"mandatory":false,"type":"none"},"saliency-maxreso":{"mandatory":false,"type":"int"},"saliency-minreso":{"mandatory":false,"type":"int"},"saliency-nn":{"mandatory":false,"type":"float"},"saliency-nooptimalthr":{"mandatory":false,"type":"none"},"saliency-resostep":{"mandatory":false,"type":"int"},"saliency-thr":{"mandatory":false,"type":"float"},"saliency-usebkgmap":{"mandatory":false,"type":"none"},"saliency-usermsmap":{"mandatory":false,"type":"none"},"saliency-userobustpars":{"mandatory":false,"type":"none"},"save-bkgmap":{"mandatory":false,"type":"none"},"save-inputmap":{"mandatory":false,"type":"none"},"save-regions":{"mandatory":false,"type":"none"},"save-residualmap":{"mandatory":false,"type":"none"},"save-rmsmap":{"mandatory":false,"type":"none"},"save-saliencymap":{"mandatory":false,"type":"none"},"save-segmentedmap":{"mandatory":false,"type":"none"},"save-significancemap":{"mandatory":false,"type":"none"},"seedthr":{"mandatory":false,"type":"float"},"seedthrstep":{"mandatory":false,"type":"float"},"selectsources":{"mandatory":false,"type":"none"},"smoothfilter":{"mandatory":false,"type":"int"},"sourcebkgboxborder":{"mandatory":false,"type":"int"},"sp-beta":{"mandatory":false,"type":"float"},"sp-minarea":{"mandatory":false,"type":"int"},"sp-size":{"mandatory":false,"type":"int"},"submit":{"mandatory":false,"type":"none"},"tilesize":{"mandatory":false,"type":"int"},"tilestep":{"mandatory":false,"type":"float"},"wtscalemax":{"mandatory":false,"type":"int"},"wtscalemin":{"mandatory":false,"type":"int"},"xmax":{"mandatory":false,"type":"int"},"xmin":{"mandatory":false,"type":"int"},"ymax":{"mandatory":false,"type":"int"},"ymin":{"mandatory":false,"type":"int"}}
```

### **Job submission**
* URL:```http://server-address:port/caesar/api/v1.0/job```   
* Request methods: POST   
* Request header: ```content-type: application/json```   

A sample curl request would be:   

```
curl -X POST \   
  -H 'Content-Type: application/json' \   
  -d '{"app":"sfinder","job_inputs":{"inputfile":"/opt/caesar-rest/data/67a49bf7555b41739095681bf52a1f99.fits","run":true,"no-logredir":true,"envfile":"/home/riggi/Software/setvars.sh","no-mpi":true,"no-nestedsearch":true,"no-extendedsearch":true}}' \   
  --url 'http://localhost:8080/caesar/api/v1.0/job'   
```

Job data must contain a valid app name (in this case `sfinder`) and desired job inputs, e.g. a dictionary with app valid options. Valid options for `sfinder` app are named as in `caesar` and can be retrieved using app description url described above.   

Server response is:   

```
{
  "app": "sfinder",
  "job_id": "69ca62d7-5098-4fe7-a675-63895a2d06b1",
  "job_inputs": {
    "envfile": "/home/riggi/Software/setvars.sh",
    "inputfile": "/opt/caesar-rest/data/67a49bf7555b41739095681bf52a1f99.fits",
    "no-extendedsearch": true,
    "no-logredir": true,
    "no-mpi": true,
    "no-nestedsearch": true,
    "run": true
  },
  "status": "Job submitted with success",
  "submit_date": "2020-04-24T14:05:24.761766"
}
```

A job id is returned in the response which can be used to query the status of the job or cancel it or retrieve output data at completion. 

### **Get job status**
* URL:```http://server-address:port/caesar/api/v1.0/job/[job_id]/status```   
* Request methods: GET   
* Request header: None   

A sample curl request would be:   

```
curl -X GET \   
  --url 'http://localhost:8080/caesar/api/v1.0/job/f135bcee-562b-4f01-ad9b-103c35b13b36/status'   
```

Server response is:   

```
{
  "elapsed_time": "27.3435878754",
  "exit_status": 0,
  "job_id": "f135bcee-562b-4f01-ad9b-103c35b13b36",
  "pid": "11539",
  "state": "SUCCESS",
  "status": "Process terminated with success"
}
```

Exit status is the shell exit status of background task executed and pid the corresponding process id. Possible job states are: {STARTED, TIMED-OUT, ABORTED, RUNNING, SUCCESS, FAILURE}. 


### **Get job output**
* URL:```http://server-address:port/caesar/api/v1.0/job/[job_id]/output```   
* Request methods: GET   
* Request header: None   

A sample curl request would be:   

```
curl -X GET \   
  --fail -o job_output.tar.gz \
  --url 'http://localhost:8080/caesar/api/v1.0/job/c3c9348a-bea0-4141-8fe9-7f64076a2327/output'   
```

The response is a tar.gz file containing all job directory files (logs, output data, run scripts, etc).  

### **Cancel job**

WRITE ME
