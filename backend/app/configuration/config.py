import os

_logs_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "logs"))
os.makedirs(_logs_dir, exist_ok=True)

class ConfigSettings:
    LOGGING_PATH = os.path.join(_logs_dir, "app.log")
