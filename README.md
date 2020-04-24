# caesar-rest
Rest API for caesar source finder application based on Flask framework [https://palletsprojects.com/p/flask/]. Celery task queue is used to execute caesar application jobs asynchronously. In this application Celery is configured by default to use a RabbitMQ broker for message exchange and Redis as task result store. 

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

### **Package installation**
To build and install the package:    

* Create a local install directory, e.g. ```$INSTALL_DIR```
* Add installation path to your ```PYTHONPATH``` environment variable:   
  ``` export PYTHONPATH=$PYTHONPATH:$INSTALL_DIR/lib/python2.7/site-packages ```
* Build and install package:   
  ``` python setup install --prefix=$INSTALL_DIR```   

All dependencies will be automatically downloaded and installed in ```$INSTALL_DIR```.   
     
To use package scripts:

* Add binary directory to your ```PATH``` environment variable:   
  ``` export PATH=$PATH:$INSTALL_DIR/bin ```    

## **Run the application**  

To run:

* Run rabbitmq service:  
   ```systemctl start rabbitmq-server.service```   
* Run redis service:    
   ```systemctl status redis.service```   
* Run celery worker with desired concurrency level (e.g. 2):    
   ```celery -A caesar_rest worker --loglevel=INFO --concurrency=2```   
* Run caesar-rest application:    
  ```$INSTALL_DIR/bin/run_app.sh```   

## **Usage**  

