import logging
import os

# Get the absolute path to the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Create logs directory if it doesn't exist
logs_dir = os.path.join(script_dir, 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

def setup_logging():
    """Configure logging with file and console handlers."""
    logger = logging.getLogger('hafiscal')
    
    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.INFO)

    # Create handlers
    file_handler = logging.FileHandler(os.path.join(logs_dir, 'hafiscal.log'))
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatters and add it to the handlers
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False

    return logger

# Get logger instance
logger = setup_logging()

def log_figure_saved(filepath):
    """Log when a figure is saved to a file."""
    logger.info(f"Figure saved to: {filepath}") 