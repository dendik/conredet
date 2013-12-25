[ -z "$2" ] && echo "Use: $0 '\$14 <= 60' image.png table" && exit 1

filter="$1"
image="$2"
table="$3"

if [ "$2" = "all" ]; then
	for table in tables6/*; do
		name="${table%-occ*}"; name="${name#*/}"
		echo "$name"
		"$0" "$filter" "img6/$name/tmp-border.png" "$table"
		"$0" "$filter" "img6/$name/tmp-norm.png" "$table"
	done
	exit
fi

out="${2}.discarded.png"
draw="$(
	awk "$filter" "$table" | grep -v spot \
		| awk '{ print "circle " $2 "," $3 " " $2 "," ($3 - 10) }'
)"
convert "$image" -draw "fill none stroke-width 2 stroke red $draw" "$out"

out="${2}.discarded-cross.png"
draw="$(
	awk "$filter" "$table" | grep -v spot \
		| awk '{ print "M " $2 "," $3 " l -7,-7 14,14 -7,-7 l -7,7 14,-14 -7,7 "}' \
		| sed "s/.*/path '&'/"
)"
convert "$image" -draw "fill none stroke-width 2 stroke red $draw" "$out"
