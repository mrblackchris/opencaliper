"""Application icon and native desktop/taskbar identity."""
from pathlib import Path
import sys
from PySide6 import QtGui


APP_ID = 'org.opencaliper.OpenCaliper'
ICON_PATH = Path(__file__).with_name('assets') / 'opencaliper.png'


def application_icon():
    """Load the packaged logo; Qt supplies the appropriate native icon size."""
    return QtGui.QIcon(str(ICON_PATH))


def configure_windows_identity():
    """Give Windows a stable taskbar group instead of the generic Python identity."""
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
