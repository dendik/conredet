import optparse
import glob
import sys
from PIL import Image
from analyze import Images, Spots, log, print_sizes_and_occupancies

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

log("Filtering spots...")
spots.filter_by_size(options.min_spot_size, options.max_spot_size)

log("Building spot neighborhoods...")
green_boxes = spots.expanded((0, options.green_box_size, options.green_box_size))
green_boxes.assign_cube(images.cubes[1])

log("Normalizing spot neighborhoods...")
images.cubes[1] = green_boxes.normalized_cube(options.nucleus_quantile,
	options.nucleus_set_level)

log("Saving temporary image...")
for spot in spots.spots:
	images.cubes[0][spot] = 255
images.cubes[2] = ((images.cubes[1] > options.chromosome_level) * 255).astype('uint8')
images.from_cubes()
images.flattened().save('tmp2.png')
images.save("tmp-{n:02}.png")

log("Counting occupancies & sizes...")
oses = {}
espots = Spots(spots).assign_cube(images.cubes[1])
oses[0] = espots.sizes_and_occupancies(options.chromosome_level)
for size in range(1, 3+1):
	ospots = espots
	espots = espots.expanded()
	oses[size] = (espots - ospots).sizes_and_occupancies(options.chromosome_level)
oses[25] = spots.expanded((0, 25, 25)).sizes_and_occupancies(options.chromosome_level)

log("Writing...")
if options.out_occupancies:
	sys.stdout = open(options.out_occupancies, 'w')
print_sizes_and_occupancies(spots, oses)

log("... done!")
