import os
import matplotlib as mpl
from logging_config import logger, log_figure_saved

def ensure_dir_exists(filepath):
    """Ensure the directory for the given filepath exists."""
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def get_version_suffix():
    """Get the version suffix from the version file if it exists."""
    version_file = os.path.join(os.path.dirname(__file__), 'version')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            content = f.read().strip()
            if content:  # If file is not empty
                return content
    return ''  # Return empty string if file doesn't exist or is empty

# Check if display is available
def has_display():
    try:
        # Check if DISPLAY is set (Unix-like systems)
        if os.name == 'posix':
            return bool(os.environ.get('DISPLAY', None))
        # On Windows, assume display is available
        return os.name == 'nt'
    except:
        return False

# Configure matplotlib based on environment
try:
    # Try to use TkAgg if we have a display
    if has_display():
        mpl.use('TkAgg')
        import matplotlib.pyplot as plt
        plt.ion()  # Turn on interactive mode
    else:
        mpl.use('Agg')  # Fallback to non-interactive backend
        import matplotlib.pyplot as plt
except Exception:
    # If all else fails, use Agg
    mpl.use('Agg')
    import matplotlib.pyplot as plt

# Helper function for showing plots that works in both interactive and non-interactive modes
def show_plot(block=False, save_path=None):
    """
    Display a plot if possible, otherwise just save it.
    
    Args:
        block (bool): Whether to block execution when showing the plot
        save_path (str): If provided, save the figure to this path
    """
    try:
        if save_path:
            # Get version suffix
            version_suffix = get_version_suffix()
            
            # Modify save path if version suffix exists
            if version_suffix:
                # Split path into directory, filename, and extension
                directory = os.path.dirname(save_path)
                filename = os.path.basename(save_path)
                name, ext = os.path.splitext(filename)
                
                # Add version suffix before extension
                new_filename = f"{name}{version_suffix}{ext}"
                save_path = os.path.join(directory, new_filename)
            
            # Ensure the directory exists
            ensure_dir_exists(save_path)
            
            # Save the figure
            plt.savefig(save_path)
            log_figure_saved(save_path)
            
        if has_display():
            plt.show(block=block)
        plt.close()  # Clean up the figure
    except Exception as e:
        logger.error(f"Error in show_plot: {str(e)}")
        plt.close()  # Clean up the figure even if there's an error
        raise