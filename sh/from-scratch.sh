#!/bin/sh
export run_name=6
export blurred=blurred$run_name
export flat=flat$run_name
export tables=tables$run_name
export img=img$run_name

./merge-all.sh
./remove-bad.sh
./chr-control.sh
./copy-images.sh
