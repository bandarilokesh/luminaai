import logging
import sys
import psutil
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config.settings import settings

class SystemStatsFilter(logging.Filter):
    """Filter that injects system CPU and Memory usage statistics into log records."""
    def filter(self, record):
        process = psutil.Process()
        memory_info = process.memory_info()
        record.cpu_percent = psutil.cpu_percent()
        # Convert bytes to megabytes (MB)
        record.memory_usage_mb = memory_info.rss / (1024 * 1024)
        return True

def setup_logger(name: str = "lumina_ai") -> logging.Logger:
    """Sets up a structured rotating file and console logger with performance diagnostics."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if setup multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Create logs directory if not already created
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = settings.LOG_DIR / "app.log"
    
    # Configure formatter with performance context
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] "
        "[CPU: %(cpu_percent).1f%%] [MEM: %(memory_usage_mb).2fMB] - %(message)s"
    )
    
    # Inject system stats filter
    stats_filter = SystemStatsFilter()
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(stats_filter)
    
    # Rotating File Handler (10MB files, keeping 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(stats_filter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Prevent propagation to the root logger
    logger.propagate = False
    
    return logger

# Global default logger
logger = setup_logger()
