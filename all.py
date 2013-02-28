import optparse
import glob
import sys
from PIL import Image
from analyze import Images, Spots, log

p = optparse.OptionParser()
p.add_option("-i", "--images")
p.add_option("--red-spot-level", type=int, default=120)
p.add_option("--min-spot-size", type=int, default=15)
p.add_option("--max-spot-size", type=int, default=500)
p.add_option("--green-box-size", type=int, default=25)
p.add_option("--nucleus-quantile", type=float, default=0.5)
p.add_option("--nucleus-set-level", type=int, default=100)
p.add_option("--chromosome-level", type=int, default=150)
p.add_option("--out-occupancies")
options, args = p.parse_args()

log("Loading images...")
images = Images(glob.glob(options.images))
log("Converting to numpy...")
images.assign_cubes()
log("Detecting spots...")
spots = Spots(images.cubes[0])
#spots.assign_pixels(options.red_spot_leve).filter_tight_pixels()
spots.detect_cc(options.red_spot_level)

#log(sorted(spots.pixels, key=lambda(z,y,x):(z,x,y)))
#log("Saving temporary image...")
#im = Image.new('RGB', images.images[0].size)
#spots.draw_flat(im)
#im.save('tmp.png')

print spots.assign_sizes().sizes[0]
print spots.spots[0]
print spots.cube[spots.spots[0]]

log("Filtering spots...")
spots.filter_by_size(options.min_spot_size, options.max_spot_size)

log("Normalizing spots...")
green_boxes = spots.expanded((0, options.green_box_size, options.green_box_size))
green_boxes.cube = images.cubes[1]
images.cubes[1] = green_boxes.normalized_cube(options.nucleus_quantile,
	options.nucleus_set_level)

log("Counting occupancies & sizes...")
def sizes_and_occupancies(spots):
	return (spots.assign_sizes().sizes,
		spots.occupancies(options.chromosome_level))

oses = {}
espots = Spots(spots)
espots.cube = images.cubes[1]
oses[0] = sizes_and_occupancies(espots)
for size in range(1, 3+1):
	espots = espots.expanded()
	oses[size] = sizes_and_occupancies(espots - spots)
espots = spots.expanded((0, 25, 25))
oses[25] = sizes_and_occupancies(espots)

log("Writing...")
if options.out_occupancies:
	outfile = open(options.out_occupancies, 'w')
else:
	outfile = sys.stdout

print >>outfile, "spot",
for size in sorted(oses):
	print >>outfile, "size" + str(size), "occupancy" + str(size),
print >>outfile

for n in spots.ids():
	print >>outfile, n,
	for size in sorted(oses):
		print >>outfile, oses[n][0], oses[n][1],
	print >>outfile

log("... done!")
