import os

bind = "0.0.0.0:" + os.environ.get("PORT", "5001")
workers = 2
timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"