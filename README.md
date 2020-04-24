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

  ```$INSTALL_DIR/bin/run_app.sh --[ARGS]```

where supported `ARGS` are:    

   * `datadir=[DATADIR]`: Directory where to store uploaded data (default: /opt/caesar-rest/data)   
   * `jobdir=[JOBDIR]`: Top directory where to store job data (default: /opt/caesar-rest/data)
   * `debug`: Run Flask application in debug mode if given   
   
Flask default options are defined in the `config.py`. Celery options are defined in the `celery_config.py`.

### **Run the application in production**   


## **Usage**  
caesar-rest by default will
