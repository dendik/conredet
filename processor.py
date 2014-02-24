import optparse
import os
import glob
import sys
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
from analyze import Images, Spots
from utils import log, logging

options = None
colors = [(200, 50, 50), (200, 100, 0), (200, 0, 100), (150, 200, 0)]

def main():
	global options
	options, args = parse_options()
	log(options.red)
	log(options.green)
	log(options.blue)
	images = load_images()

	draw_flat_images(images, "img-src.png")
	spotss = {}
	normalized = Normalized(images)
	for color_options in options.signal:
		this = spotss[color_options.color] = detect_signals(images, color_options)
		draw_flat_spots(images, "img-c{color}.png", this, color_options)
		draw_flat_border(images, "img-b{}.png".format(color_options.color), this)
		neighborhoods = build_neighborhoods(this, images)
		normalized.add(normalize_neighborhoods(neighborhoods, images))
	images = normalized.get()
	territories = spotss['territory'] = detect_signals(images, options.territory)
	draw_flat_images(images, "img-normalized.png")
	draw_flat_border(images, "img-bterritories.png", territories)
	draw_flat_colors(images, "img-cterritories.png", territories, colors)
	images.save("img-{n:02}.png")
	draw_3D_colors(images, "img-c{n:02}.png", spotss)
	print_stats(spotss, images)

# --------------------------------------------------
# Input & preprocessing
#

@logging
def load_images():
	if options.images:
		images = Images(glob.glob(options.images))
		images.assign_cubes()
	elif options.czi_images:
		import czifile
		with czifile.CziFile(options.czi_images) as czi:
			images = load_czi_images(czi)
			print_czi_metadata(czi)
	return images

def load_czi_images(czi):
	images = Images()
	universe = czi.asarray()
	r, p, g, b = [universe[j,0,:,:,:,0] for j in range(4)]
	images.from_cubes([r, g, b])
	return images

def print_czi_metadata(czi):
	colors = 'Red', '(ignore)', 'Green', 'Blue'
	channels = czi.metadata.findall(".//ExcitationWavelength")
	for n, (channel, color) in enumerate(zip(channels, colors)):
		wavelength = str(int(float(channel.text))) + "nm"
		log(n, channel.getparent().get('Name'), wavelength, "=>", color)
	for coord in "XYZ":
		scaling, = czi.metadata.findall(".//Scaling" + coord)
		log(coord, "scaling:", int(float(scaling.text) * 10**9), "nm")

@logging
def detect_signals(images, options):
	spots = Spots(images.cubes[options.channel])
	if options.blur:
		cube = images.cubes[options.channel].astype('float')
		cube = gaussian_filter(cube, options.blur)
		spots = Spots(cube.astype('uint8'))
	#spots.assign_pixels(options.level).filter_tight_pixels()
	spots.detect_cc(options.level)
	spots.filter_by_size(options.min_size, options.max_size)
	return spots

@logging
def build_neighborhoods(spots, images):
	size = options.neighborhood_size
	neighborhoods = spots.expanded((0, size, size))
	neighborhoods.assign_cube(images.cubes[options.territory.channel])
	return neighborhoods

@logging
def normalize_neighborhoods(neighborhoods, images):
	channel = options.territory.channel
	stretch_quantiles = options.neighborhood_stretch_quantiles
	shift_quantile = options.neighborhood_shift_quantile
	level = options.neighborhood_set_level

	save = neighborhoods.cube = images.cubes[channel]
	if stretch_quantiles is not None:
		cube = neighborhoods.cube = neighborhoods.stretched_cube(*stretch_quantiles)
	if shift_quantile:
		cube = neighborhoods.normalized_cube(shift_quantile, level)
	images.cubes[channel] = neighborhoods.cube = save
	return cube

class Normalized(object):
	def __init__(self, images):
		self.images = images
		self.channel = options.territory.channel
		self.cube = np.zeros(images.cubes[self.channel].shape, 'uint8')
	def add(self, cube):
		self.cube = np.maximum(self.cube, cube)
	def get(self):
		self.images.cubes[self.channel] = self.cube
		self.images.from_cubes()
		return self.images

# --------------------------------------------------
# Output
#

@logging
def print_stats(spotss, images):
	stats = count_all_overlaps(spotss, images)

	if options.out_stats:
		sys.stdout = open(options.out_stats, 'w')

	for key in sorted(stats):
		name1, name2, size = key
		spots = spotss[name1]
		centers = map(lambda xyz: map(int, xyz), spots.centers())
		zs, ys, xs = zip(*centers)
		sizes, occupancies = stats[key]
		print ""
		print name1, name2, size
		print "spot", "x", "y", "z", "size", "occupancy"
		for n in spotss[name1].ids():
			print n, xs[n], ys[n], zs[n], sizes[n], occupancies[n]

def count_all_overlaps(spotss, images):
	stats = {}
	for color in spotss:
		espots = Spots(spotss[color])
		for size in options.spot_sizes:
			eespots = espots.expanded((0, size, size))
			for other in spotss:
				if other != color:
					count_channel_overlaps(stats, images, eespots, color, other, size)
	return stats

	###TODO: This part is not yet reproduced:
	#for size in range(1, 3+1):
	#	ospots = espots
	#	espots = espots.expanded((0, 1, 1))
	#	oses[size] = (espots - ospots).sizes_and_occupancies(options.chromosome_level)

@logging
def count_channel_overlaps(stats, images, spots, name1, name2, size):
	color_options = vars(options)[name2]
	spots.assign_cube(images.cubes[color_options.channel])
	sizes_and_occupancies = spots.sizes_and_occupancies(color_options.level)
	stats[name1, name2, size] = sizes_and_occupancies

# --------------------------------------------------
# Images output
#

@logging
def draw_flat_images(images, filename):
	images.clone().flattened().save(filename)

@logging
def draw_flat_spots(images, filename, spots, options, blackout=True):
	images = images.clone()
	if blackout:
		images.cubes[options.channel] *= 0
	for spot in spots.spots:
		images.cubes[options.channel][spot] = 255
	images.from_cubes()
	images.flattened().save(filename.format(**vars(options)))

@logging
def draw_flat_colors(images, filename, spots, colors):
	spots = Spots(spots)
	espots = Spots(spots).expanded((0,3,3)).assign_few_colors(colors, True)
	spots.colors = espots.colors
	images = images.clone()
	spots.draw_flat(images.flattened()).save(filename)

@logging
def draw_flat_border(images, filename, spots):
	spots.assign_color(options.border_color)
	spots.draw_flat_border(images.flattened()).save(filename)

@logging
def draw_3D_border(images, filename, spots):
	images = images.clone()
	spots = spots.expanded((0, 1, 1)) - spots
	spots.draw_3D(images)
	images.save(filename)

@logging
def draw_3D_colors(images, filename, spotss):
	images = images.clone()
	for name in spotss:
		color_options = vars(options)[name]
		for spot in spotss[name].spots:
			images.cubes[color_options.channel][spot] = 255
	images.from_cubes()
	images.save(filename)

# --------------------------------------------------
# Option parsing
#

def parse_options():
	p = optparse.OptionParser()
	p.add_option("-i", "--images", help="glob expression for images")
	p.add_option("-z", "--czi-images", help="czi file with images")
	p.add_option("-o", "--out-stats", help="outfile with stats (default: stdout)")
	for color in ("--red", "--green", "--blue"):
		p.add_option(color + "-role", help="Either of: empty, signal, territory")
		p.add_option(color + "-level", default=120, type=int,
			help="Minimal signal level on this channel")
		p.add_option(color + "-min-size", default=15,
			type=int, help="Minimal size of spot")
		p.add_option(color + "-max-size", default=500,
			type=int, help="Maximal size of spot")
		p.add_option(color + "-blur", type=float,
			help="If non-zero, apply gausian blur; use parameter value as sigma")
	p.add_option("--neighborhood-size", default=25, type=int,
		help="Size (approx. half the side of square) of spot neighborhood")
	p.add_option("--neighborhood-stretch-quantiles",
		help="Comma-separated list of lower & upper quantile values to stretch")
	p.add_option("--neighborhood-set-level", default=100, type=int,
		help="Level of detected signal in neighborhood (used by next option)")
	p.add_option("--neighborhood-shift-quantile", type=float,
		help="Shift values to make this quantile equal neighborhood-set-level")
	p.add_option("--spot-sizes", default=(0, 1, 3),
		help="Comma-separated list of spot extension sizes to report occupancy on")
	p.add_option("--border-color", default=(255, 160, 80),
		help="Color for border, given as r,g,b values in range 0 to 255")

	parse_environment_defaults(p)
	options, args = p.parse_args()

	if (options.neighborhood_stretch_quantiles is None
			and options.neighborhood_shift_quantile is None):
		options.neighborhood_shift_quantile = 0.5

	parse_tuple_options(options)
	split_color_options(options)
	parse_color_list_options(options)

	return options, args

def parse_environment_defaults(optparser):
	for option in optparser.defaults:
		default = os.environ.get(option.upper(), optparser.defaults[option])
		optparser.defaults[option] = default
	return optparser

def parse_tuple_option(options, name, size=None, type=float):
	value = getattr(options, name)
	if isinstance(value, str):
		value = tuple(map(type, value.split(",")))
	if size is not None:
		assert len(value) == size
	setattr(options, name, value)

def parse_tuple_options(options):
	parse_tuple_option(options, 'neighborhood_stretch_quantiles', size=2)
	parse_tuple_option(options, 'spot_sizes', type=int)
	parse_tuple_option(options, 'border_color', size=3, type=int)

def split_color_options(options):
	for n, color in enumerate(("red", "green", "blue")):
		color_options = optparse.Values()
		color_options.channel = n
		color_options.color = color
		for option, value in vars(options).items():
			if option.startswith(color + "_"):
				option = option.split("_", 1)[-1]
				setattr(color_options, option, value)
		setattr(options, color, color_options)

def parse_color_list_options(options):
	options.signal = []
	options.territory = None
	for color_options in (options.red, options.green, options.blue):
		if color_options.role == "signal":
			options.signal.append(color_options)
		elif color_options.role == "territory":
			assert options.territory is None
			options.territory = color_options

if __name__ == "__main__":
	main()
