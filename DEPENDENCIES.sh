#!/bin/sh
wget -nc \
	http://www.lfd.uci.edu/~gohlke/code/czifile.py \
	http://www.lfd.uci.edu/~gohlke/code/czifile.pyx

wget --no-check-certificate \
	http://raw.github.com/timmywil/jquery.panzoom/2.0.5/dist/jquery.panzoom.min.js \
	-O static/jquery.panzoom.js

wget --no-check-certificate \
	http://raw.githubusercontent.com/jquery/jquery-mousewheel/master/jquery.mousewheel.min.js \
	-O static/jquery.mousewheel.js
