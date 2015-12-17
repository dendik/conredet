#!/usr/bin/env python
import optparse
import os
import glob
import sys
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter, maximum_filter
from PIL import Image
import tifffile

from analyze import Images, Spots
from utils import log, log_dict, logging, ifverbose, roundint, Re, dict_path

options = None
colors = [(200, 50, 50), (200, 100, 0), (200, 0, 100), (150, 200, 0)]
option_colors = dict(red=0, green=1, blue=2, red2=0, green2=1, blue2=2)
draw_colors = ('red2', 'green', 'blue')
onion_colors = ('red',)
cell_color = 'red2'

def main():
	global options
	global images # see XXX in detect_signals
	options, args = parse_options()
	start()

def start():
	global images # see XXX in detect_signals
	for color in sorted(options.color):
		log_dict(vars(options.color[color]))
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
	print_scale(images)
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
			spotss[color] = Spots(cube, images=images)

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
# Input
#

def load_images():
	if options.images:
		images = load_glob_images(options.images)
	elif options.czi_images:
		images = load_czi_images(options.czi_images)
	elif options.nd2_images:
		images = load_nd2_images(options.nd2_images)
	elif options.lsm_images:
		images = load_lsm_images(options.lsm_images)
	elif options.tiff_images:
		images = load_tiff_images(options.tiff_images)
	return images

@logging
def load_glob_images(filename):
	assert options.channels == 'rgb', "Channel ordering unsupported in RGB images"
	images = Images(glob.glob(filename))
	images.assign_cubes()
	images.wavelengths = None
	images.scale = None
	return images

@logging
def load_czi_images(filename):
	import czifile
	with czifile.CziFile(filename) as czi:
		images = Images()
		universe = czi.asarray()
		channels = {}
		for j, name in enumerate(options.channels):
			channels[name] = universe[j,0,:,:,:,0]
		images.from_cubes([channels['r'], channels['g'], channels['b']])
		load_czi_metadata(images, czi)
		return images

def load_czi_metadata(images, czi):
	wavelengths = czi.metadata.findall(".//ExcitationWavelength")
	log('wavelengths', *wavelengths)
	channels = {}
	for name, value in zip(options.channels, wavelengths):
		channels[name] = float(value)
	images.wavelengths = (channels['r'], channels['g'], channels['b'])
	images.scale = tuple(
		10**9 * float(czi.metadata.findall(".//Scaling" + coord)[0].text)
		for coord in "ZYX"
	)

@logging
def load_nd2_images(filename):
	with open(filename) as file:
		nd2 = open_nd2(file)
		data = [nd2.get_image(n)[1:] for n in range(nd2.Z)]
		data = (np.array(data) >> 4).astype('uint8')
		data = data.reshape((nd2.Z, data.shape[1], nd2.H, nd2.W))
		channels = {}
		for n, channel in enumerate(options.channels):
			channels[channel] = data[:, n, :, :]
		images = Images()
		images.from_cubes([channels['r'], channels['g'], channels['b']])
		load_nd2_metadata(nd2, images)
	return images

def open_nd2(file):
	from sloth.read_nd2 import Nd2File
	nd2 = Nd2File(file)
	vars(nd2).update(nd2.attr)
	nd2.Z = nd2.uiSequenceCount
	nd2.H = nd2.uiHeight
	nd2.W = nd2.uiWidth
	nd2.scalexy = dict_path(nd2.meta, 'SLxCalibration/dCalibration')
	nd2.scalez = dict_path(nd2.meta, 'SLxExperiment/uLoopPars/dZStep')
	return nd2

def load_nd2_metadata(nd2, images):
	images.wavelengths = nd2_wavelengths(nd2)
	images.scale = (
		nd2.scalez * 1000,
		nd2.scalexy * 1000,
		nd2.scalexy * 1000
	)

def nd2_wavelengths(nd2):
	planes = dict_path(nd2.meta, 'SLxPictureMetadata/sPicturePlanes/sPlane')
	tail = 'pFilterPath/m_pFilter//m_ExcitationSpectrum/pPoint/Point0/dWavelength'
	wavelengths = {}
	for name, plane in zip(options.channels, sorted(planes)):
		wavelengths[name] = float(dict_path(planes[plane], tail))
		log('wavelength', name, wavelengths[name])
	return wavelengths['r'], wavelengths['g'], wavelengths['b']

@logging
def load_lsm_images(filename):
	lsm = tifffile.TIFFfile(filename)
	meta_page, = (page for page in lsm.pages if page.is_lsm)
	meta = meta_page.cz_lsm_scan_info
	images = load_tiff_images(None, tiff=lsm)
	images.wavelengths = lsm_wavelengths(meta)
	images.scale = lsm_scale(meta)
	return images

def lsm_wavelengths(meta_page):
	wavelengths = [
		channel['wavelength']
		for track in meta_page['tracks']
		for channel in track['illumination_channels']
		if channel.get('acquire', channel.get('aquire'))
	]
	log('wavelengths', *wavelengths)
	wavelengths = dict(zip(options.channels, wavelengths))
	return wavelengths['r'], wavelengths['g'], wavelengths['b']

def lsm_scale(meta_page):
	return (
		meta_page['plane_spacing'] * 1000,
		meta_page['sample_spacing'] * 1000, # or plane_height / images_height
		meta_page['line_spacing'] * 1000, # or plane_width / images_width
	)

@logging
def load_tiff_images(filename, tiff=None):
	tiff = tiff or tifffile.TIFFfile(filename)
	data = tiff_to_czxy(tiff)
	if data.dtype != 'uint8': # force conversion to uint8 with stretching
		data = (data.astype('float') / data.max() * 255).astype('uint8')
	channels = dict(zip(options.channels, data))
	images = Images().from_cubes([channels['r'], channels['g'], channels['b']])
	images.wavelengths = (0, 0, 0)
	images.scale = (0, 0, 0)
	return images

def tiff_to_czxy(tiff):
	data = tiff.asarray()
	if len(data.shape) ==  5 and data.shape[0] == 1: # XXX HACK for LSM
		data = data[0]
	assert len(data.shape) == 4 # should be ZCXY
	return data.swapaxes(0, 1)

# --------------------------------------------------
# Preprocessing
#

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
	global images # XXX: the code is too messy to get images any other way
	spots = Detectors(cube, options, images).spots
	spots.filter_by_size(options.min_size, options.max_size)
	return spots

class Detectors(object):
	def __init__(self, cube, options, images):
		self.spots = Spots(cube, images=images)
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
def print_scale(images):
	meta = {}
	meta.update(dict(zip("rgb", images.wavelengths)))
	meta.update(dict(zip("zyx", images.scale)))
	print "x", "y", "z", "r", "g", "b", "unit"
	print " ".join('{:.2f}'.format(meta[name]) for name in"xyzrgb"), "nm"

@with_output
@logging
def print_signals(spotss):
	print "cell_n", "color", "spot", "x", "y", "z", "size", "volume"
	for cell_n, cell in iter_cells(spotss):
		print_signal_stats(cell_n, 'red2', cell_n, cell)
		for color, spot_n, spot in iter_cell_spots(spotss, cell):
			print_signal_stats(cell_n, color, spot_n, spot)

def print_signal_stats(cell_n, color, spot_n, spot):
	z, y, x = ('{:.2f}'.format(coord) for coord in spot.center_of_mass())
	size = spot.size()
	volume = spot.to_physical_volume(size)
	print cell_n, color, spot_n, x, y, z, size, volume

@with_output
@logging
def print_pairs(spotss):
	print "cell_n", "color1", "spot1", "color2", "spot2",
	print "distance", "physical_distance", "onion_distance",
	print "overlap", "overlap_volume"
	for cell_n, cell in iter_cells(spotss):
		for color1, spot_n1, spot1 in iter_cell_spots(spotss, cell):
			for color2, spot_n2, spot2 in iter_cell_spots(spotss, cell):
				if spot1 == spot2:
					continue
				print cell_n, color1, spot_n1, color2, spot_n2,
				print " ".join("{:.2f}".format(value) for value in [
					spot1.distance(spot2), spot1.physical_distance(spot2),
					onion_distance(spot1, color1, spotss[color2]),
				] + list(overlap(spot1, spot2)))

def onion_distance(spot1, color1, spots2):
	if color1 not in onion_colors:
		return -2
	onion_distance = spot1.distance_to_variety(spots2, d=(0, 1, 1))
	if onion_distance is None:
		return -1
	# scale properly, assuming resolution by X is the same as by Y
	onion_distance *= spot1.spots.images.scale[-1]
	return onion_distance

def overlap(spot1, spot2):
	spots = Spots(spot2.spots.cube)
	spots.spots = [spot2]
	overlap = spot1.intersection_occupancy(spots)
	physical_overlap = spot1.to_physical_volume(overlap)
	return overlap, physical_overlap

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

def option_parser():
	p = optparse.OptionParser()
	p.add_option("-i", "--images", help="glob expression for images")
	p.add_option("-z", "--czi-images", help="czi file with images")
	p.add_option("-n", "--nd2-images", help="nd2 file with images")
	p.add_option("-t", "--tiff-images", help="tiff file with images")
	p.add_option("-l", "--lsm-images", help="lsm file with images")
	p.add_option("-c", "--channels", default="rgb",
		help="specify order in which image channels are used, - for not used")
	p.add_option("-S", "--out-scale", help="file with scale & wavelength metadata")
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
	return p

def parse_options():
	p = option_parser()
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
