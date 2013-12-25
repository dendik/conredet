#!/bin/sh
for im in {CCND1,MLL_{0h,1h{,_repeat1,_repeat2_{cto,vto}}}}-{c,e}; do
	tail -q -n +2 tables2/$im-* > tables2/sum-$im.xls
done
