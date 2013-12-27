import optparse
import os
import glob
import sys
from PIL import Image
from analyze import Images, Spots, log, print_sizes_and_occupancies

p = optparse.OptionParser()
p.add_option("-i", "--images", help="glob expression for image names")
p.add_option("-z", "--czi-images", help="czi-file with images")
p.add_option("--red-spot-level", type=int, default=120)
p.add_option("--min-spot-size", type=int, default=15)
p.add_option("--max-spot-size", type=int, default=500)
p.add_option("--green-box-size", type=int, default=25)
p.add_option("--green-noise-level", type=int, default=0)
p.add_option("--nucleus-quantile", type=float, default=0.5)
p.add_option("--stretch-quantiles")
p.add_option("--nucleus-set-level", type=int, default=100)
p.add_option("--chromosome-level", type=int, default=150)
p.add_option("-o", "--out-occupancies")
for option in p.defaults:
	p.defaults[option] = os.environ.get(option.upper(), p.defaults[option])
options, args = p.parse_args()

if options.stretch_quantiles:
	q1, q2 = map(float, options.stretch_quantiles.split(","))
	options.stretch_quantiles = q1, q2

log("Loading images...")
if options.images:
	images = Images(glob.glob(options.images))
	images.assign_cubes()
elif options.czi_images:
	import czifile
	images = Images()
	with czifile.CziFile(options.czi_images) as czi:
		universe = czi.asarray()
		r, p, g, b = [universe[j,0,:,:,:,0] for j in range(4)]
		images.from_cubes([b, r, g])

if not options.green_noise_level:
	log("Saving temporary image...")
	images.flattened().save('tmp-src.png')

log("Detecting spots...")
spots = Spots(images.cubes[0])
#spots.assign_pixels(options.red_spot_level).filter_tight_pixels()
spots.detect_cc(options.red_spot_level)

log("Filtering spots...")
spots.filter_by_size(options.min_spot_size, options.max_spot_size)

log("Saving temporary image...")
#spots.assign_few_colors([(0,0,255), (0,0,128), (0,255,0)], True)
#spots.draw_flat(images.flattened()).save('tmp-red.png')
for spot in spots.spots:
	images.cubes[2][spot] = 255
images.from_cubes()
images.flattened().save('tmp-red.png')

log("Building spot neighborhoods...")
green_boxes = spots.expanded((0, options.green_box_size, options.green_box_size))
green_boxes.assign_cube(images.cubes[1])

if options.green_noise_level:
	log("Removing noise...")
	green_boxes.cube *= green_boxes.cube > options.green_noise_level

	log("Saving temporary image...")
	images.cubes[2] *= 0
	images.from_cubes()
	images.flattened().save('tmp-src.png')

log("Normalizing spot neighborhoods...")
if options.stretch_quantiles is not None:
	images.cubes[1] = green_boxes.stretched_cube(*options.stretch_quantiles)
	green_boxes.cube = images.cubes[1]
if options.nucleus_quantile:
	images.cubes[1] = green_boxes.normalized_cube(options.nucleus_quantile,
		options.nucleus_set_level)

log("Saving temporary image...")
images.cubes[2] *= 0
for spot in spots.spots:
	images.cubes[2][spot] = 255
images.from_cubes()
chr_spots = Spots(images.cubes[1])
chr_spots.detect_cc(options.chromosome_level)
chr_spots.assign_color((255, 160, 80))
chr_spots.draw_flat_border(images.flattened()).save('tmp-border.png')

log("Saving temporary image...")
images.flattened().save('tmp-norm.png')
for spot in spots.spots:
	images.cubes[0][spot] = 255
images.cubes[2] = ((images.cubes[1] > options.chromosome_level) * 255).astype('uint8')
images.from_cubes()
images.flattened().save('tmp-spots.png')
images.save("tmp-{n:02}.png")

log("Counting occupancies & sizes...")
oses = {}
espots = Spots(spots).assign_cube(images.cubes[1])
oses[0] = espots.sizes_and_occupancies(options.chromosome_level)
oses[10] = espots.expanded((0, 10, 10)).sizes_and_occupancies(options.chromosome_level)
oses[15] = espots.expanded((0, 15, 15)).sizes_and_occupancies(options.chromosome_level)
oses[20] = espots.expanded((0, 20, 20)).sizes_and_occupancies(options.chromosome_level)
oses[25] = espots.expanded((0, 25, 25)).sizes_and_occupancies(options.chromosome_level)
for size in range(1, 3+1):
	ospots = espots
	espots = espots.expanded((0, 1, 1))
	oses[size] = (espots - ospots).sizes_and_occupancies(options.chromosome_level)

log("Writing...")
if options.out_occupancies:
	sys.stdout = open(options.out_occupancies, 'w')
print_sizes_and_occupancies(spots, oses)

log("... done!")
