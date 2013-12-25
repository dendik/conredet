#!/bin/sh
convert -size 1024x1024 xc:black black.png
#convert -size 2048x2048 xc:black black.png
trap "rm black.png" EXIT
blurred="${blurred:-blurred}"
merged="${merged:-merged}"
mkdir -p "$blurred" "$merged"

for image in ../{CCND,MLL}*/*/*/RED/*; do
	oifs="$IFS"; IFS=/; set -- $image; IFS="$oifs"
	shift
	series="$1"
	case "$2" in C*|c*) type=c;; *) type=e;; esac
	num="$3"; num="${num%_ccnd1}"; num="${num%_mll_?h}";
	im="$5"; im="${im#${im%??.png}}"; im="${im%.png}";
	out="$series-$type-$num-im-$im.png"
	red="$image"
	#green="$image"; green="${green/RED/GREEN}"; green="${green/C3/C2}"; green="${green/experiment3/experiment4}"
	green="${image%/$4/$5}"/GREEN/*$im.png; green="`ls $green`"
	blue=black.png

	if ! [ -e "$red" -a -e "$green" ]; then
		echo MISSING GREEN for "$red"
		continue
	fi

	if [ ! -e "$merged/$out" ]; then
		echo "merged $out <- $red & $green"
		convert \
			"$red" -channel r -separate \
			"$green" -channel g -separate \
			"$blue" -channel b -separate \
			-channel rgb -combine \
			"$merged/$out"
	fi

	if [ ! -e "$blurred/$out" ]; then
		echo "blurred $out <- $red & $green"
		convert \
			"$red" -channel r -separate \
			"$green" -channel g -separate \
			"$blue" -channel b -separate \
			-channel rgb -combine \
			-channel g -gaussian-blur 0x2 \
			"$blurred/$out"
		# convert "$merged/$out" -channel g -gaussian-blur 5x5 "$blurred/$out"
	fi

	## [ -e normalized/$out ] && continue
	## echo "$out <- $red & $green"
	## convert \
	## 	"$red" "$green" "$blue" \
	## 	-channel rgb -combine \
	## 	-channel r 
	## 	-channel g -gaussian-blur 5x5 \
	## 	"normalized/$out"
	## #for i in *; do echo $i; convert $i -channel r -contrast-stretch 0 -channel g -contrast-stretch 0 ../normalized/$i; done

done
