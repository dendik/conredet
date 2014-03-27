import optparse
import os
import glob
import sys
import re
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter, maximum_filter
from PIL import Image
from analyze import Images, Spots
from utils import log, logging, roundint

options = None
colors = [(200, 50, 50), (200, 100, 0), (200, 0, 100), (150, 200, 0)]
option_colors = dict(red=0, green=1, blue=2, red2=0, green2=1, blue2=2)
draw_colors = ('red', 'green', 'blue')

def main():
	global options
	options, args = parse_options()
	for color in sorted(options.color):
		log(options.color[color])
	images = load_images()

	draw_flat_images(images, "img-src.png")
	draw_3D_images(images, "img-{n:02}.png")
	despeckle_images(images)
	#draw_3D_images(images, "img-f{n:02}.png")

	spotss = {}
	normalized = Normalized(images)
	process_colors(spotss, images, options.signal, normalized)

	images = normalized.get()
	draw_flat_images(images, "img-normalized.png")

	process_colors(spotss, images, options.territories)

	draw_flat_channels(images, "img-colors.png", spotss)
	draw_3D_colors(images, "img-c{n:02}.png", spotss)
	print_stats(spotss, images)
	print_spots(spotss)

def process_colors(spotss, images, colors, normalized=None):
	for color_options in colors:
		log("I'm going slightly", color_options.color, "...")
		cube = detection_filters(images, color_options)
		this = spotss[color_options.color] = detect_signals(cube, color_options)
		draw_flat_border(images, "img-b{}.png".format(color_options.color), this)
		if normalized:
			neighborhoods = build_neighborhoods(this, images)
			normalized.add(normalize_neighborhoods(neighborhoods, images))

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
def despeckle_images(images):
	for color_options in options.color.values():
		channel = color_options.channel
		cube = images.cubes[channel]
		if color_options.despeckle:
			cube = median_filter(cube, (3,1,1))
		images.cubes[channel] = cube
	return images.from_cubes()

@logging
def detect_signals(cube, options):
	spots = Spots(cube)
	if options.tight:
		spots.assign_pixels(options.level).filter_tight_pixels(options.tight)
	spots.detect_cc(options.level)
	spots.filter_by_size(options.min_size, options.max_size)
	return spots

class Re(object):
	had_match = False
	def __init__(self, text):
		self.text = text
	def __call__(self, expr):
		self.match = re.match(expr, self.text)
		self.had_match = self.had_match or self.match
		return self.match
	def get(self, group=1, func=(lambda x: x), default=None):
		return func(self.match.group(group) or default)
	def __getitem__(self, arg):
		return self.get(*arg)

@logging
def detection_filters(images, options):
	cube = src_cube = images.cubes[options.channel].astype('float')
	if options.blur:
		arg = Re(text=options.blur.replace(' ', ''))
		if arg(r'peak.*\(([0-9.]*)(?:,([0-9]*))?\)'):
			sigma, side = arg[1, float, 1], arg[2, int, 3]
			blur_cube = gaussian_filter(cube, sigma)
			max_cube = maximum_filter(blur_cube, (side, side * 3, side * 3))
			cube = (cube - blur_cube) * 100 / max_cube
			#draw_3D_cubes((cube, blur_cube, max_cube), 't-%s-{n:02}.png' % options.color)
			draw_flat_cubes([cube, blur_cube, max_cube], 'blur-{}.png'.format(options.color))
		if arg(r'gauss.*\(([0-9.]*)\)'):
			cube = gaussian_filter(cube, arg[1, float, 1])
			draw_flat_cube(cube, 'blur-{}.png'.format(options.color))
		assert arg.had_match, 'invalid syntax in --{}-blur'.format(options.color)
	return cube.clip(0, 255).astype('uint8')

@logging
def build_neighborhoods(spots, images):
	size = options.neighborhood_size
	neighborhoods = spots.expanded((0, size, size))
	neighborhoods.assign_cube(images.cubes[options.normalize_channel])
	return neighborhoods

@logging
def normalize_neighborhoods(neighborhoods, images):
	channel = options.normalize_channel
	stretch_quantiles = options.neighborhood_stretch_quantiles
	shift_quantile = options.neighborhood_shift_quantile
	level = options.neighborhood_set_level

	save = answer = neighborhoods.cube = images.cubes[channel]
	if stretch_quantiles is not None:
		answer = neighborhoods.cube = neighborhoods.stretched_cube(*stretch_quantiles)
	if shift_quantile:
		answer = neighborhoods.normalized_cube(shift_quantile, level)
	images.cubes[channel] = neighborhoods.cube = save
	return answer

class Normalized(object):
	def __init__(self, images):
		self.images = images
		self.channel = options.normalize_channel
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
	if options.out_stats:
		sys.stdout = open(options.out_stats, 'w')

	for color1, color2, size, spots, color_options in iter_views(spotss):
		print ""
		print color1, color2, size
		print "spot", "x", "y", "z", "size", "occupancy"
		spots.assign_cube(images.cubes[color_options.channel])
		for n, spot in enumerate(spots.spots):
			z, y, x = map(roundint, spot.center())
			print n, x, y, z, spot.size(), spot.occupancy(color_options.level)

def iter_views(spotss):
	for color in spotss:
		for size in options.spot_sizes:
			espots = Spots(spotss[color]).expanded((0, size, size))
			for other_color in spotss:
				if other_color != color:
					yield color, other_color, size, espots, options.color[other_color]

@logging
def print_spots(spotss):
	if options.out_spots:
		sys.stdout = open(options.out_spots, 'w')
	
	for color in spotss:
		for other in spotss:
			if other == color:
				continue
			print
			print color, other, "intersected-ids"
			other_spots = spotss[other]
			for n, spot in enumerate(spotss[color].spots):
				ids = spot.intersection_ids(other_spots)
				print n, " ".join(map(str, ids))

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
		images.cubes[options.channel][spot.coords] = 255
	images.from_cubes()
	images.flattened().save(filename.format(**vars(options)))

@logging
def draw_flat_colors(images, filename, spots, colors):
	spots = Spots(spots)
	espots = Spots(spots).expanded((0,3,3)).assign_few_colors(colors, True)
	spots.assign_colors_from(espots, True)
	images = images.clone()
	spots.draw_flat(images.flattened()).save(filename)

@logging
def draw_flat_channels(images, filename, spotss):
	spots_by_channels(images, spotss).flattened().save(filename)

@logging
def draw_flat_border(images, filename, spots):
	spots.assign_color(options.border_color, True)
	spots.draw_flat_border(images.flattened()).save(filename)

@logging
def draw_flat_cubes(cubes, filename):
	cubes = [cube.clip(0, 255).astype('uint8') for cube in cubes]
	Images().from_cubes(cubes).flattened().save(filename)

def draw_flat_cube(cube, filename):
	draw_flat_cubes([cube, cube, cube], filename)

@logging
def draw_3D_cubes(cubes, filename):
	cubes = [cube.clip(0, 255).astype('uint8') for cube in cubes]
	Images().from_cubes(cubes).save(filename)

@logging
def draw_3D_images(images, filename):
	images.save(filename)

@logging
def draw_3D_border(images, filename, spots):
	images = images.clone()
	border = spots.expanded((0, 1, 1))
	border -= spots
	border.draw_3D(images)
	images.save(filename)

@logging
def draw_3D_colors(images, filename, spotss):
	spots_by_channels(images, spotss).save(filename)

def spots_by_channels(images, spotss):
	images = images.clone()
	for name in spotss:
		color_options = options.color[name]
		for spot in spotss[name].spots:
			if name in draw_colors:
				images.cubes[color_options.channel][spot.coords] = 255
	return images.from_cubes()

# --------------------------------------------------
# Option parsing
#

def parse_options():
	p = optparse.OptionParser()
	p.add_option("-i", "--images", help="glob expression for images")
	p.add_option("-z", "--czi-images", help="czi file with images")
	p.add_option("-o", "--out-stats", help="outfile with stats (default: stdout)")
	p.add_option("-s", "--out-spots", help="outfile with spots (default: stdout)")
	for color in sorted(option_colors):
		color = "--" + color
		p.add_option(color + "-role",
			help="Either of: empty, signal, territory, core")
		p.add_option(color + "-level", default=120, type=int,
			help="Minimal signal level on this channel")
		p.add_option(color + "-min-size", default=15,
			type=int, help="Minimal size of spot")
		p.add_option(color + "-max-size", default=500,
			type=int, help="Maximal size of spot")
		p.add_option(color + "-blur",
			help="Apply filters. Either gauss(sigma) or peak(sigma, [side])")
		p.add_option(color + "-tight", type=int,
			help="Require that much pixels in neighborhood to add pixel to signal")
		p.add_option(color + "-despeckle", type=int,
			help="Apply median filter before any processing")
	p.add_option("--normalize-channel", default=0, type=int)
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
	if value == "":
		value = None
	if isinstance(value, str):
		value = tuple(map(type, value.split(",")))
	if value is not None and size is not None:
		assert len(value) == size
	setattr(options, name, value)

def parse_tuple_options(options):
	parse_tuple_option(options, 'neighborhood_stretch_quantiles', size=2)
	parse_tuple_option(options, 'spot_sizes', type=int)
	parse_tuple_option(options, 'border_color', size=3, type=int)

def split_color_options(options):
	options.color = {}
	for color in option_colors:
		color_options = optparse.Values()
		color_options.channel = option_colors[color]
		color_options.color = color
		for option, value in vars(options).items():
			if option.startswith(color + "_"):
				option = option.split("_", 1)[-1]
				setattr(color_options, option, value)
		options.color[color] = color_options

def parse_color_list_options(options):
	options.signal = []
	options.territories = []
	for color in tuple(options.color):
		color_options = options.color[color]
		if color_options.role in (None, '', 'empty'):
			del options.color[color]
		elif color_options.role == 'signal':
			options.signal.append(color_options)
		elif color_options.role == 'territory':
			options.territories.append(color_options)

if __name__ == "__main__":
	main()
