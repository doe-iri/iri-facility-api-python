import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

workers = 8
worker_class = "uvicorn.workers.UvicornWorker" 
bind = "0.0.0.0:8000"
timeout = 60
