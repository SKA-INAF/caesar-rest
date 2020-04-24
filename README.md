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

### **Run backend services**
To run caesar-rest you must first run the message broker, the task store and worker services:

* Run rabbitmq message broker service:  
   ```systemctl start rabbitmq-server.service```   
* Run redis store service:    
   ```systemctl status redis.service```   
* Run celery worker with desired concurrency level (e.g. 2):    
   ```celery -A caesar_rest worker --loglevel=INFO --concurrency=2```   
   
### **Run the application in development mode**   
To run caesar-rest in development mode, e.g. for debug or testing purposes:   

  ```$INSTALL_DIR/bin/run_app.py --[ARGS]```

where supported `ARGS` are:    

   * `datadir=[DATADIR]`: Directory where to store uploaded data (default: /opt/caesar-rest/data)   
   * `jobdir=[JOBDIR]`: Top directory where to store job data (default: /opt/caesar-rest/data)
   * `debug`: Run Flask application in debug mode if given   
   
Flask default options are defined in the `config.py`. Celery options are defined in the `celery_config.py`. Other options may be defined in the future to override default Flask and Celery options.   

### **Run the application in production**   
In a production environment you can run the application behind a nginx+uwsgi (or nginx+gunicorn) server. For example:  

* Start the application with uwsgi:   
     
  ```uwsgi --wsgi-file $INSTALL_DIR/bin/run_app.py --callable app [WSGI_CONFIG_FILE]```

  where `WSGI_CONFIG_FILE` is a configuration file (.ini format) for uwsgi. A sample configuration file is provided in the `config` directory. You can run the application as system service as described below:
  
  WRITE ME    
  

* Specify nginx server configuration in file . A possible configuration file `/etc/nginx/conf.d/nginx.conf`(see example file provided in the `config` directory) include:   

  ```
  server {   
	  listen 8080;    
	  location / {   
		  include uwsgi_params;    
		  uwsgi_pass flask:5000;    
	  }    
  }    
  ```
  
  With this sample configuration the nginx server will listen at port 8080 and call the caesar-rest application at port 5000. 
   
* Run nginx server:   

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



