import logging
from configuration.config import ConfigSettings as CS

def get_logging_conf():
    
    logging.basicConfig(filename=CS.LOGGING_PATH, level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s : %(lineno)d")
    
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger('schedule').propagate = False
    logging.getLogger('werkzeug').disabled = True
    
    return logging