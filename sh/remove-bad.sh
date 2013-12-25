#!/bin/sh
blurred="${blurred:-blurred}"
cd "$blurred"

# Remove malsized images
echo -e '\e[31;7m'
echo REMOVING:
ls -1 *-im-??-?.png
echo -e '\e[0m'
rm *-im-??-?.png

# Unaligned RED/GREEN
rm MLL_1h_repeat1-c-1-im*.png
rm MLL_1h_repeat2_cto-e-1-im*.png

# Entirely black / after image with bottom half black
rm CCND1-{c,e}-2-im-13.png
rm MLL_0h-c-1-im-{10..13}.png
rm MLL_0h-c-3-im-{12..14}.png
rm MLL_0h-e-1-im-{11..14}.png
rm MLL_1h_repeat2_cto-e-3-im-{12..14}.png

# Extremely noisy
#rm MLL_1h-c-1-im-{10..13}.png
#rm MLL_1h-c-2-im-{00..01}.png
#rm MLL_1h-c-2-im-13.png
#rm MLL_1h-c-3-im-{12..13}.png
#rm MLL_1h-c-4-im-{10..13}.png
