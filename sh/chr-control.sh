#!/bin/sh
bin=~/projects/rubtsov/

f () {
	f="$1"; shift
	echo $f...
	python "$bin/all.py" \
		-i "blurred/$f*" \
		-o "tables/$f-occupancies.xls" \
		"$@"
	mkdir -p img/$f
	mv tmp* img/$f
	echo ...$f
	echo
}

export MIN_SPOT_SIZE=16
export MAX_SPOT_SIZE=400
export NUCLEUS_SET_LEVEL=130
export GREEN_NOISE_LEVEL=0

export RED_SPOT_LEVEL=40
export CHROMOSOME_LEVEL=150
export NUCLEUS_QUANTILE=0.5
f CCND1-c-1
f CCND1-c-2
f CCND1-c-3 --chromosome-level=155
f CCND1-e-1 ## bad quality
f CCND1-e-2 --red-spot-level=60 # unfinished
f CCND1-e-3 # unfinished
f CCND1-e-4 # unfinished
f CCND1-e-5 # unfinished

export RED_SPOT_LEVEL=60
export NUCLEUS_QUANTILE=0.45
export CHROMOSOME_LEVEL=145
#ser2
f MLL_0h-c-1
f MLL_0h-c-2
f MLL_0h-c-3
export RED_SPOT_LEVEL=80
export NUCLEUS_QUANTILE=0.5
export CHROMOSOME_LEVEL=140
f MLL_0h-e-1
f MLL_0h-e-2
f MLL_0h-e-3

export CHROMOSOME_LEVEL=160
export RED_SPOT_LEVEL=160
export NUCLEUS_QUANTILE=0.5
#ser1
f MLL_1h-c-1
f MLL_1h-c-2
f MLL_1h-c-3
f MLL_1h-c-4
export CHROMOSOME_LEVEL=140
export RED_SPOT_LEVEL=50
export NUCLEUS_QUANTILE=0.4
f MLL_1h-e-1 --nucleus-quantile=0.5
f MLL_1h-e-2
f MLL_1h-e-3
f MLL_1h-e-4 --red-spot-level=40

export CHROMOSOME_LEVEL=150
export RED_SPOT_LEVEL=80
export NUCLEUS_QUANTILE=0.5
f MLL_1h_repeat1-c-2
f MLL_1h_repeat1-c-3
export NUCLEUS_QUANTILE=0.4
f MLL_1h_repeat1-e-1
f MLL_1h_repeat1-e-2
f MLL_1h_repeat1-e-3
f MLL_1h_repeat1-e-4
f MLL_1h_repeat1-e-5

export CHROMOSOME_LEVEL=160
export RED_SPOT_LEVEL=70
export NUCLEUS_QUANTILE=0.45
f MLL_1h_repeat2_cto-c-1
f MLL_1h_repeat2_cto-c-2
f MLL_1h_repeat2_cto-c-3
export NUCLEUS_QUANTILE=0.6
f MLL_1h_repeat2_cto-e-2
f MLL_1h_repeat2_cto-e-3 --red-spot-level=80

export RED_SPOT_LEVEL=70
export CHROMOSOME_LEVEL=140
export NUCLEUS_QUANTILE=0.5
f MLL_1h_repeat2_vto-c-1 --chromosome-level=145
f MLL_1h_repeat2_vto-c-2
f MLL_1h_repeat2_vto-c-3 --red-spot-level=80 --chromosome-level=135
f MLL_1h_repeat2_vto-e-1
f MLL_1h_repeat2_vto-e-2
f MLL_1h_repeat2_vto-e-3
