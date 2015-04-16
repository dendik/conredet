import optparse
import os
import glob
import sys
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter, maximum_filter
from PIL import Image

from analyze import Images, Spots
from utils import log, logging, ifverbose, roundint, Re

options = None
colors = [(200, 50, 50), (200, 100, 0), (200, 0, 100), (150, 200, 0)]
option_colors = dict(red=0, green=1, blue=2, red2=0, green2=1, blue2=2)
draw_colors = ('red2', 'green', 'blue')
cell_color = 'red2'

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
	images = smart(spotss, images, options)
	draw_flat_images(images, "img-normalized.png")

	#spotss = {}
	#normalized = Normalized(images)
	#process_colors(spotss, images, options.signal, normalized)

	#images = normalized.get()
	#draw_flat_images(images, "img-normalized.png")

	#process_colors(spotss, images, options.territories)

	draw_flat_channels(images, "img-colors.png", spotss)
	draw_3D_colors(images, "img-c{n:02}.png", spotss)
	print_results(spotss, images)

def process_colors(spotss, images, colors, normalized=None):
	for color_options in colors:
		log("I'm going slightly", color_options.color, "...")
		cube = detection_filters(images, color_options)
		this = spotss[color_options.color] = detect_signals(cube, color_options)
		draw_flat_border(images, "img-b{}.png".format(color_options.color), this)
		if normalized and options.neighborhood_size:
			neighborhoods = build_neighborhoods(this, images)
			normalized.add(normalize_neighborhoods(neighborhoods, images))

@logging
def print_results(spotss, images):
	print_signals(spotss)
	print_pairs(spotss)
	print_stats(spotss, images)
	print_spots(spotss)
	print_distances(spotss)

# --------------------------------------------------
# Alternative (hopefully) smart processing
#

def smart(spotss, images, options):
	images = detect_cells(spotss, images, options)
	prefill_spotss(spotss, images)
	for n, cell in enumerate(spotss[cell_color].spots):
		log(n, "...")
		for color, color_options in options.color.items():
			if color == cell_color:
					continue
			cube = select_cube(images, color_options, cell)
			spots = smart_color(cube, color_options)
			spotss[color_options.color].spots += spots.spots
	smart_draw(spotss, images, options)
	return images

def detect_cells(spotss, images, options):
	log("Detecting cells...")
	color_options = options.color[cell_color]
	cube = detection_filters(images, color_options)
	this = spotss[cell_color] = detect_signals(cube, color_options)
	if options.neighborhood_size:
		neighborhoods = build_neighborhoods(this, images)
		images.cubes[options.normalize_channel] = normalize_neighborhoods(neighborhoods, images)
	return images

def prefill_spotss(spotss, images):
	for color in tuple(options.color):
		if color not in spotss:
			cube = images.cubes[options.color[color].channel]
			spotss[color] = Spots(cube)

def select_cube(images, color_options, cell):
	src_cube = images.cubes[color_options.channel]
	cube = np.zeros_like(src_cube)
	cube[cell.coords] = src_cube[cell.coords]
	return cube

def smart_color(cube, color_options):
	cube = cube.astype('float')
	if color_options.blur:
		blur, color = color_options.blur, color_options.color
		cube = Filters(cube, blur, color, False).cube
	cube = cube.clip(0, 255).astype('uint8')
	return detect_signals(cube, color_options)

def smart_draw(spotss, images, options):
	for color in spotss:
		draw_flat_border(images, "img-b{}.png".format(color), spotss[color])

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
	elif options.nd2_images:
		with open(options.nd2_images) as file:
			images = load_nd2_images(file)
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

def load_nd2_images(file):
	nd2 = open_nd2(file)
	data = [nd2.get_image(n)[1:] for n in range(nd2.Z)]
	data = (np.array(data) >> 4).astype('uint8')
	data = data.reshape((nd2.Z, data.shape[1], nd2.H, nd2.W))
	## XXX: hopefully, contrast is always channel 4 or absent
	g, b, r = [data[:, n, :, :] for n in range(3)]
	images = Images()
	images.from_cubes([r, g, b])
	print_nd2_metadata(nd2)
	return images

def open_nd2(file):
	from sloth.read_nd2 import Nd2File
	nd2 = Nd2File(file)
	vars(nd2).update(nd2.attr)
	nd2.Z = nd2.uiSequenceCount
	nd2.H = nd2.uiHeight
	nd2.W = nd2.uiWidth
	nd2.scalexy = nd2.meta['SLxCalibration']['dCalibration']
	nd2.scalez = nd2.meta['SLxExperiment']['uLoopPars']['dZStep']
	return nd2

def print_nd2_metadata(nd2):
	colors = 'Green', 'Blue', 'Red', '(ignore)',
	wavelengths = nd2_wavelengths(nd2)
	for n, (wavelength, color) in enumerate(zip(wavelengths, colors)):
		log(n, wavelength, 'nm', "=>", color)
	log('X', "scaling:", int(nd2.scalexy * 10**3), "nm")
	log('Y', "scaling:", int(nd2.scalexy * 10**3), "nm")
	log('Z', "scaling:", int(nd2.scalez * 10**3), "nm")

def nd2_wavelengths(nd2):
	return [
		(nd2.meta['SLxPictureMetadata']['sPicturePlanes']['sPlane']
			.get(c, {}).get('pFilterPath', {}).get('m_pFilter', {})
			.get('', {}).get('m_EmissionSpectrum', {}).get('pPoint', {})
			.get('Point0', {}).get('dWavelength'))
			for c in ('a0', 'a1', 'a2', 'a3')]

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
	spots = Detectors(cube, options).spots
	spots.filter_by_size(options.min_size, options.max_size)
	return spots

class Detectors(object):
	def __init__(self, cube, options):
		self.spots = Spots(cube)
		self.options = options
		for func in options.detect.split(';'):
			eval('self.' + func)

	def tight(self, level, tightness):
		self.spots.assign_pixels(level).filter_tight_pixels(tightness)
		self.cc(level)

	def cc(self, level):
		self.spots.detect_cc(level)

	def percentile(self, percentile):
		level = np.percentile(self.spots.cube, percentile)
		self.spots.detect_cc(level)

	def topvoxels(self, voxels):
		where = self.spots.cube.argpartition(-voxels, axis=None)[-voxels]
		level = self.spots.cube.flat[where]
		self.spots.detect_cc(level)

	def spheres(self, n, radius, wipe_radius=None):
		self.spots.detect_spheres(n, radius, wipe_radius or radius)

	def cylinders(self, n, radius, wipe_radius=None):
		self.spots.detect_cylinders(n, radius, wipe_radius or radius)

class Filters(object):

	def __init__(self, cube, string, color, draw=True):
		self.cube = self.src_cube = cube
		self.cubes = None
		self.color = color
		self.draw = draw
		for func in string.split(';'):
			eval('self.' + func)
		if draw:
			draw_flat_cubes(self.cubes or [self.cube] * 3,
				'blur-{}-all.png'.format(self.color))
			#draw_3D_cubes((cube, blur_cube, max_cube),
			#	'blur-%s-{n:02}.png' % self.color)

	def peak(self, sigma, side=3):
		if isinstance(side, int):
			side = (side, side * 3, side * 3)
		blur_cube = gaussian_filter(self.cube, sigma)
		max_cube = maximum_filter(blur_cube, side)
		self.cube = (self.cube - blur_cube) * 100 / max_cube
		self.cubes = [self.cube, blur_cube, max_cube]

	def peak1(self, sigma=2, sides=(1,99,99)):
		no_peaks = gaussian_filter(self.cube, sigma)
		background = maximum_filter(no_peaks, sides)
		self.cube = self.cube / (background + 1) * 100

	def peak2(self, sigma=2, sides1=(1,11,11), sides2=(3,99,99)):
		no_peaks = gaussian_filter(self.cube, sigma)
		background1 = maximum_filter(no_peaks, sides1)
		background2 = maximum_filter(no_peaks, sides2)
		cube1 = self.cube / (background1 + 1)
		cube2 = self.cube / (background2 + 1)
		self.cube = cube1 * cube2 * 100

	def peak3(self, sigma=2, sides=(1,99,99), w_near=1, w_far=1):
		no_peaks = gaussian_filter(self.cube, sigma)
		background = maximum_filter(no_peaks, sides)
		cube1 = self.cube / no_peaks
		cube2 = no_peaks / background
		self.cube = (cube1 ** 2 * w_near + cube2 ** 2 * w_far) / (w_near + w_far) * 100

	def gauss(self, sigma):
		self.cube = gaussian_filter(self.cube, sigma)

	def max(self, dx, dy=None, dz=None):
		if dy is None or dz is None:
			dx, dy, dz = dx * 3, dx * 3, dx
		self.cube = maximum_filter(self.cube, (dz, dy, dx))

	def median(self, dx, dy=None, dz=None):
		if dy is None or dz is None:
			dx, dy, dz = dx * 3, dx * 3, dx
		self.cube = median_filter(self.cube, (dz, dy, dx))

@logging
def detection_filters(images, options):
	cube = images.cubes[options.channel].astype('float')
	if options.blur:
		cube = Filters(cube, options.blur, options.color).cube
		draw_flat_cube(cube, 'blur-{}.png'.format(options.color))
	return cube.clip(0, 255).astype('uint8')

@logging
def build_neighborhoods(spots, images):
	size = options.neighborhood_size
	neighborhoods = spots.ellipsoids((size/3, size, size))
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

def with_output(function):
	filename_option = 'out_' + function.func_name.replace("print_", "")
	filename = lambda: vars(options)[filename_option]
	def result(*args, **kwargs):
		if not filename():
			return
		backup_stdout = sys.stdout
		sys.stdout = open(filename(), 'w')
		function(*args, **kwargs)
		sys.stdout = backup_stdout
	return result

@with_output
@logging
def print_signals(spotss):
	print "cell_n", "color", "spot", "x", "y", "z", "size"
	for cell_n, cell in iter_cells(spotss):
		for color, spot_n, spot in iter_cell_spots(spotss, cell):
			z, y, x = ('{:.2f}'.format(coord) for coord in spot.center_of_mass())
			size = spot.size()
			print cell_n, color, spot_n, x, y, z, size

@with_output
@logging
def print_pairs(spotss):
	print "cell_n", "color1", "spot1", "color2", "spot2", "distance"
	for cell_n, cell in iter_cells(spotss):
		for color1, spot_n1, spot1 in iter_cell_spots(spotss, cell):
			for color2, spot_n2, spot2 in iter_cell_spots(spotss, cell):
				if spot1 != spot2:
					print cell_n, color1, spot_n1, color2, spot_n2,
					print spot1.distance(spot2)

def iter_cells(spotss):
	for cell_n, cell in enumerate(spotss[cell_color].spots):
			yield cell_n, cell

def iter_cell_spots(spotss, cell):
	for color in spotss:
		if color == cell_color:
			continue
		spots = spotss[color]
		for spot_n in cell.intersection_ids(spots):
			yield color, spot_n, spots.spots[spot_n]

@with_output
@logging
def print_stats(spotss, images):
	for color1, color2, size, spots, other in iter_views(spotss):
		print ""
		print color1, color2, size
		print "spot", "x", "y", "z", "size", "occupancy"
		for n, spot in enumerate(spots.spots):
			z, y, x = ('{:.2f}'.format(coord) for coord in spot.center())
			print n, x, y, z, spot.size(), spot.intersection_occupancy(other)

def iter_views(spotss):
	for color in spotss:
		for size in options.spot_sizes:
			espots = Spots(spotss[color]).expanded((0, size, size))
			for other_color in spotss:
				if other_color != color:
					other = spotss[other_color]
					yield color, other_color, size, espots, other

@with_output
@logging
def print_spots(spotss):
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

@with_output
@logging
def print_distances(spotss):
	for color in ('blue', 'green'):
		for other in ('red',):
			if other == color:
				continue
			print
			print color, other, "extend", "ellipsoid"
			other_spots = spotss[other]
			for n, spot in enumerate(spotss[color].spots):
				print n,
				print spot.distance_to_variety(other_spots, d=(0, 1, 1)) or -1,
				print spot.center_to_variety(other_spots, d=(0.3, 1, 1)) or -1,
				print

# --------------------------------------------------
# Images output
#

@ifverbose
@logging
def draw_flat_images(images, filename):
	images.clone().flattened().save(filename)

@ifverbose
@logging
def draw_flat_spots(images, filename, spots, options, blackout=True):
	images = images.clone()
	if blackout:
		images.cubes[options.channel] *= 0
	for spot in spots.spots:
		images.cubes[options.channel][spot.coords] = 255
	images.from_cubes()
	images.flattened().save(filename.format(**vars(options)))

@ifverbose
@logging
def draw_flat_colors(images, filename, spots, colors):
	spots = Spots(spots)
	espots = Spots(spots).expanded((0,3,3)).assign_few_colors(colors, True)
	spots.assign_colors_from(espots, True)
	images = images.clone()
	spots.draw_flat(images.flattened()).save(filename)

@ifverbose
@logging
def draw_flat_channels(images, filename, spotss):
	spots_by_channels(images, spotss).flattened().save(filename)

@logging
def draw_flat_border(images, filename, spots):
	spots.assign_color(options.border_color, True)
	spots.draw_flat_border(images.flattened()).save(filename)

@ifverbose
@logging
def draw_flat_cubes(cubes, filename):
	cubes = [cube.clip(0, 255).astype('uint8') for cube in cubes]
	Images().from_cubes(cubes).flattened().save(filename)

def draw_flat_cube(cube, filename):
	draw_flat_cubes([cube, cube, cube], filename)

@ifverbose
@logging
def draw_3D_cubes(cubes, filename):
	cubes = [cube.clip(0, 255).astype('uint8') for cube in cubes]
	Images().from_cubes(cubes).save(filename)

@ifverbose
@logging
def draw_3D_images(images, filename):
	images.save(filename)

@ifverbose
@logging
def draw_3D_border(images, filename, spots):
	images = images.clone()
	border = spots.expanded((0, 1, 1))
	border -= spots
	border.draw_3D(images)
	images.save(filename)

@ifverbose
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
	p.add_option("-n", "--nd2-images", help="nd2 file with images")
	p.add_option("-1", "--out-signals", help="file with per-signal data")
	p.add_option("-2", "--out-pairs", help="file with per-pair data")
	p.add_option("-o", "--out-stats", help="obsolete file with stats")
	p.add_option("-s", "--out-spots", help="obsolete file with spots")
	p.add_option("-d", "--out-distances", help="obsolete distances outfile")
	for color in sorted(option_colors):
		color = "--" + color
		p.add_option(color + "-role",
			help="Either of: empty, signal, territory, core")
		p.add_option(color + "-detect", default='cc(120)',
			help="Detection functions. Default: cc(120)."
			" Alternatives: cc(level), tight(level, tightness)"
			", spheres(N, radius[, wipe]), cylinders(N, radius[, wipe])")
		p.add_option(color + "-min-size", default=15,
			type=int, help="Minimal size of spot")
		p.add_option(color + "-max-size", default=500,
			type=int, help="Maximal size of spot")
		p.add_option(color + "-blur",
			help="Apply filters. Either gauss(sigma) or peak(sigma, [side])")
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
	p.add_option("--verbose", action="store_true",
		help="Be more verbose: produce more logging & write images")

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
