#!/bin/sh
bin=~dendik/projects/rubtsov/
blurred="${blurred:-blurred}"
img="${img:-img}"
tables="${tables:-tables}"
mkdir -p "$tables" "$img"

f () {
	f="$1"; shift
	echo $f...
	python "$bin/all.py" \
		-i "$blurred/$f*" \
		-o "$tables/$f-occupancies.xls" \
		"$@"
	mkdir -p "$img/$f"
	mv tmp* "$img/$f"
	echo ...$f
	echo
}

export MIN_SPOT_SIZE=16
export MAX_SPOT_SIZE=400
export GREEN_NOISE_LEVEL=0

export STRETCH_QUANTILES=0.3,0.01
export NUCLEUS_QUANTILE=0
export CHROMOSOME_LEVEL=180

export RED_SPOT_LEVEL=40
f CCND1-c-1                      # 18 missed
f CCND1-c-2                      # 6
f CCND1-c-3                      # 6
f CCND1-e-1                      # 7
f CCND1-e-2 --red-spot-level=60  # 21
f CCND1-e-3                      # 16
f CCND1-e-4                      # 16
f CCND1-e-5                      # 17

export RED_SPOT_LEVEL=70
f CCND1_repeat1-c-1
f CCND1_repeat1-c-2
f CCND1_repeat1-c-3 --red-spot-level=50
f CCND1_repeat1-e-1
f CCND1_repeat1-e-2 --red-spot-level=60
f CCND1_repeat1-e-3 --red-spot-level=50
f CCND1_repeat1-e-4

export RED_SPOT_LEVEL=40
f CCND1_repeat2-c-1
f CCND1_repeat2-c-2
export RED_SPOT_LEVEL=70
f CCND1_repeat2-e-1
f CCND1_repeat2-e-2
f CCND1_repeat2-e-3

export RED_SPOT_LEVEL=50
f CCND1_repeat3-c-1
f CCND1_repeat3-c-2
f CCND1_repeat3-c-3
f CCND1_repeat3-e-1
f CCND1_repeat3-e-2 --red-spot-level=55
f CCND1_repeat3-e-3 --red-spot-level=55

export RED_SPOT_LEVEL=60
f MLL_0h-c-1                     # 11
f MLL_0h-c-2                     # 8
f MLL_0h-c-3                     # 5
export RED_SPOT_LEVEL=80
f MLL_0h-e-1                     # 21
f MLL_0h-e-2                     # 13
f MLL_0h-e-3                     # 14

export RED_SPOT_LEVEL=50
f MLL_0h_repeat1-c-1
f MLL_0h_repeat1-c-2
f MLL_0h_repeat1-c-3
f MLL_0h_repeat1-c-4
export RED_SPOT_LEVEL=40
f MLL_0h_repeat1-e-1
f MLL_0h_repeat1-e-2
f MLL_0h_repeat1-e-3 --red-spot-level=35
f MLL_0h_repeat1-e-4

export RED_SPOT_LEVEL=50
f MLL_0h_repeat2-c-1
f MLL_0h_repeat2-c-2
f MLL_0h_repeat2-c-3
export RED_SPOT_LEVEL=70
f MLL_0h_repeat2-e-1
f MLL_0h_repeat2-e-2
f MLL_0h_repeat2-e-3
f MLL_0h_repeat2-e-4

export RED_SPOT_LEVEL=160
f MLL_1h-c-1                     # 1 !!!
f MLL_1h-c-2                     # 1
f MLL_1h-c-3                     # 0
f MLL_1h-c-4                     # 5
export RED_SPOT_LEVEL=50
f MLL_1h-e-1                     # 4
f MLL_1h-e-2                     # 1
f MLL_1h-e-3                     # 2
f MLL_1h-e-4 --red-spot-level=40 # 2

export RED_SPOT_LEVEL=25
f MLL_1h_repeat1-c-2             # 7
f MLL_1h_repeat1-c-3             # 9
export RED_SPOT_LEVEL=60
f MLL_1h_repeat1-e-1             # 3
f MLL_1h_repeat1-e-2             # 6
f MLL_1h_repeat1-e-3             # 3
f MLL_1h_repeat1-e-4             # 9
f MLL_1h_repeat1-e-5             # 4

export RED_SPOT_LEVEL=70
f MLL_1h_repeat2_cto-c-1         # 3
f MLL_1h_repeat2_cto-c-2         # 6
f MLL_1h_repeat2_cto-c-3         # 3
f MLL_1h_repeat2_cto-e-2         # 3
f MLL_1h_repeat2_cto-e-3 --red-spot-level=80 # 1

export RED_SPOT_LEVEL=70
f MLL_1h_repeat2_vto-c-1         # 14
f MLL_1h_repeat2_vto-c-2         # 2
f MLL_1h_repeat2_vto-c-3 --red-spot-level=80 # 1
f MLL_1h_repeat2_vto-e-1         # 6
f MLL_1h_repeat2_vto-e-2         # 17
f MLL_1h_repeat2_vto-e-3         # 7
