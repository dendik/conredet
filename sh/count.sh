#!/bin/sh

for prefix in {CCND1,MLL_{0h,1h,1h_{repeat1,repeat2_{cto,vto}}}}-{c,e}; do
	echo -n "$prefix: "
	cat tables/$prefix* \
		| awk '{ if ($6 < 0.4 * $5) a += 1; else b += 1}; END { print a/NR, b/NR, "(", a, b, ")" }'
done
