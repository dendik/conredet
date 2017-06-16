JOBS	= $(PWD)/jobs
PYLIBS	= $(PWD)/pylibs
WGET	= wget --no-check-certificate

configure: jobs jobs-path $(PYLIBS) czi js

jobs:
	mkdir $(JOBS) # NB! This will take up some dozen gigabytes

jobs-path:
	sed -ri "/JOB_PREFIX =/ s@= .*@ = '$(JOBS)'@" wui.py

$(PYLIBS):
	virtualenv -p python2 $(PYLIBS)
	sed -ri "/virtualenv =/ s@= .*@'$(PYLIBS)/bin/activate_this.py'@; s@^# @@" wui_wsgi.py
	-#
	pip install numpy
	pip install scipy
	pip install python-bioformats sloth image tifffile flask

# Download czifile stuff from Christian Gholke repo.
# Version of czifile available from pip is incompatible.
#
czi: czifile.py czifile.pyx

czifile.py:
	$(WGET) -nc http://www.lfd.uci.edu/~gohlke/code/czifile.py

czifile.pyx:
	$(WGET) -nc http://www.lfd.uci.edu/~gohlke/code/czifile.pyx

# Download several javascript libraries (jquery components).
#
js: static/jquery.js static/jquery.panzoom.js static/jquery.mousewheel.js

static/jquery.js:
	$(WGET) -O $@ https://code.jquery.com/jquery-3.2.1.min.js
	
static/jquery.panzoom.js:
	$(WGET) -O $@ \
		http://raw.github.com/timmywil/jquery.panzoom/2.0.5/dist/jquery.panzoom.min.js

static/jquery.mousewheel.js:
	$(WGET) -O $@ \
		http://raw.githubusercontent.com/jquery/jquery-mousewheel/master/jquery.mousewheel.min.js
