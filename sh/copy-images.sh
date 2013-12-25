#!/bin/sh
src="${img:-img}"
run_name="${run_name:-}"

convert -size 1024x1024 xc:black black.png
convert -size 2048x2048 xc:black black2.png
trap "rm black.png black2.png" EXIT

dst=red$run_name
mkdir -p $dst
for f in $src/*; do
	i="${f##*/}"; echo $i;
	[[ f == *CCND1_repeat3* ]] && black_png=black2.png || black_png=black.png
	convert $f/*red* -separate -delete 1 $black_png -combine -gamma 2.5 $dst/$i-both.png;
	convert $f/*src* -channel r -separate +channel -gamma 3.0 $dst/$i-red.png;
	convert $f/*red* -channel b -separate $dst/$i-spot.png;
done

dst=flat$run_name
mkdir -p $dst
for f in $src/*; do
	i="${f##*/}"; echo $i;
	convert -background black merged/$i-* -compose lighten -flatten -gamma 2.0 $dst/$i-src.png;
	cp $f/*bor* $dst/$i-border.png;
done
