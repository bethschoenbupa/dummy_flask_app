import logging
from logging.handlers import RotatingFileHandler
from flask import g, has_request_context
import variables as vr

class SessionIDFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.session_id = g.get('request_id', 'unknown')
            record.path = g.get('path', 'unknown')
        else:
            record.session_id = 'unknown'
            record.path = 'unknown'
        return True

# Ensure the logs directory exists
# if not os.path.exists(vr.log_data_dir):
#     os.makedirs(vr.log_data_dir)

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a RotatingFileHandler - save to log files that will delete once they reach a certain size and number of files
# handler = RotatingFileHandler(
#     # each file is 1MB
#     # keep the last 3 files
#     os.path.join(vr.log_data_dir, vr.log_file), maxBytes=1024*1024, backupCount=3
# )

# Create a StreamHandler - display logs in the terminal
stream_handler = logging.StreamHandler()

# Create a logging format that includes session ID
formatter = logging.Formatter('Datetime %(asctime)s - Level %(levelname)s - Session ID %(session_id)s: - %(message)s')
#handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Add the handler to the logger
#logger.addHandler(handler)
logger.addHandler(stream_handler)

# Add the custom filter to the logger
session_filter = SessionIDFilter()
logger.addFilter(session_filter)