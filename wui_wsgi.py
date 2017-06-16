import sys
from os.path import dirname
sys.path.append(dirname(__file__))

## If you are using virtualenv, uncomment the following lines:
# virtualenv = '...path-to.../bin/activate_this.py'
# execfile(virtualenv, dict(__file__=virtualenv))

from wui import app as application
