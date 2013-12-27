"""

Essential workflow:

	1. load image series (as cube)
	2. R: detect intensive pixels (marker: m <= I)
	3. R: detect spots of intensive pixels together
		* bonus, if detection considers tightness (and splits collapsed pairs)
		* filter spots to have many (but not too many) pixels
	4. create n-neighbourhoods of detected spots
	5. G: normalize d-neighbourhood of detected spots
		* detect v-quantile level in neighbourhood
		* scale colors
	6. G: detect intensive pixels (chromosome area: m <= I <= M)
	7. G: calculate number of pixels in (expanded / poked) spot
	8. Save (7) as xls

Helpers:
	0. Merge R & G images into RG-image (or split RG-image into R & G images?)
	1. Save source images with detected spots
	2. Save flat image with flattened (max) source images & flattened spots
	3. Save normalized images [with detected spots & chromosome areas]

Naming:

	* images -- stack of PIL images from experiment
	* cube -- representation of series of 1-color images as a 3D numpy array

"""
import random
from itertools import izip
from PIL import Image, ImageChops
import numpy as np
from utils import log

class Spots(object):

	def __init__(self, cube, colors=None):
		if isinstance(cube, Spots):
			vars(self).update(vars(cube))
			return
		self.cube = cube
		self.pixels = set()
		self.spots = []
		self.sizes = {}
		self.colors = colors or {}

	def detect_cc(self, level):
		"""Detect spots as connected components of intensive pixels."""
		self.assign_pixels(level)
		edges = {}
		for pixel in self.pixels:
			for other in xyzvrange(pixel):
				if other in self.pixels:
					edges.setdefault(pixel, []).append(other)
		self.spots = [zip(*sorted(coords))
			for coords in find_components(edges)]
		return self

	def filter_tight_pixels(self, neighbors=15, distance=1):
		"""Remove pixels that don't have enough significant neighbors."""
		self.pixels = [pixel
			for pixel in self.pixels
			if neighbors <= len([other
				for other in xyzrange(pixel, distance)
				if other in self.pixels])]
		return self

	def filter_by_size(self, min_size, max_size):
		"""Remove spots not fitting in the given size range."""
		self.assign_sizes()
		self.spots = [spot
			for n, spot in enumerate(self.spots)
			if min_size <= self.sizes[n] <= max_size]
		return self.renumbered()

	def filter_by_height(self, min_height=2, min_presence=5):
		"""Remove spots not spanning given height."""
		spots, self.spots = self.spots, []
		for spot in spots:
			zs = Counter(z for z, y, x in izip(*spot))
			for z in zs:
				if zs[z] < min_presence:
					del zs[z]
			if len(zs) < min_height:
				continue
			self.spots.append(spot)
		return self.renumbered()

	def expanded(self, d=1):
		"""Return set of spots expanded by `d` pixels in each direction."""
		Z, Y, X = np.array(self.cube.shape)
		result = Spots(self.cube, colors=self.colors)
		for n, spot in enumerate(self.spots):
			coords = set(map(tuple, np.transpose(spot).tolist()))
			for coord in set(coords):
				coords |= set(xyzrange(coord, d))
			coords = [(z, y, x) for z, y, x in coords
				if 0 <= z < Z and 0 <= y < Y and 0 <= x < X]
			result.spots.append(zip(*sorted(coords)))
		return result

	def __sub__(self, other):
		"""Return set of spots minus pixels in `other` spots with same ids."""
		result = Spots(self.cube, colors=self.colors)
		spot2 = set()
		for spot in other.spots:
			spot2 |= set(izip(*spot))
		for spot in self.spots:
			spot1 = set(izip(*spot))
			spot3 = zip(*sorted(spot1 - spot2))
			result.spots.append(spot3)
		return result

	def assign_pixels(self, level, force=False):
		"""Detect list of coordinates of pixels above level."""
		if force or not self.pixels:
			coords = (self.cube > level).nonzero()
			self.pixels = set(izip(*coords))
		return self

	def assign_sizes(self, force=False):
		"""Return a dictionary of spot sizes."""
		if not force and self.sizes:
			return self
		self.sizes = dict((n, len(spot[0])) for n, spot in enumerate(self.spots))
		return self

	def assign_few_colors(self,
			possible_colors=[(0,255,0), (0,128,0), (0,255,128), (0,128,255)],
			force=False):
		"""Assign as few as possible colors to spots ."""
		if self.colors and not force:
			return self
		self.colors = dict((spot, possible_colors[0])
			for spot in set(self.ids()))
		spots = self.as_dict()
		for next_color in possible_colors[1:]:
			for pixel in spots:
				for other in xyzrange(pixel, 3):
					if other != pixel and other in self.spots:
						s1 = spots[pixel]
						s2 = spots[other]
						if s1 != s2 and self.colors[s1] == self.colors[s2]:
							self.colors[s1] = next_color
							break
		return self

	def assign_random_colors(self, r=None, g=None, b=None, force=False):
		"""Assign random color to each spot."""
		if self.colors and not force:
			return self
		v = lambda x: (x is None) and random.randint(128, 255) or x
		self.colors = dict((spot, (v(r), v(g), v(b))) for spot in set(self.ids()))
		return self

	def assign_color(self, color, force=False):
		"""Assigne the same color to each spot."""
		if not self.colors or force:
			self.colors = dict((spot, color) for spot in self.ids())
		return self

	def assign_cube(self, cube):
		"""Nice way of setting self.cube."""
		self.cube = cube
		return self

	def renumbered(self):
		"""Remove all data that relies on spot numbering."""
		self.colors = {}
		self.sizes = {}
		return self

	def draw_flat(self, image):
		"""Draw spots on a flat image."""
		self.draw_3D(Images(images=[image] * self.cube.shape[0]))
		return image

	def draw_3D(self, images):
		"""Draw spots on a stack of images."""
		self.assign_random_colors()
		spots = self.as_dict()
		for (x, y, z), spot in spots.iteritems():
			images.images[z].putpixel((x,y), self.colors[spot])
		return images

	def draw_flat_border(self, image):
		"""Draw perimeter of spots on a flat image."""
		flat = Spots(self)
		flat.spots = [([0]*len(Z), Y, X) for Z, Y, X in flat.spots]
		border = flat.expanded()
		border.spots = [([0]*len(Z), Y, X) for Z, Y, X in border.spots]
		border = border - flat
		return border.draw_flat(image)

	def ids(self):
		"""Return a list of available spot ids"""
		return range(len(self.spots))

	def quantiles(self, quantile):
		"""Find quantile value for each spot in `self.quantiles`."""
		values = self.values()
		quantiles = {}
		for spot in values:
			value = values[spot]
			quantiles[spot] = value[int(quantile * len(value))]
		return quantiles

	def values(self):
		"""Return dict of sorted list of pixel values in each spot."""
		values = {}
		for n, spot in enumerate(self.spots):
			values[n] = sorted(self.cube[spot].tolist())
		return values

	def normalized_cube(self, quantile=0.75, level=100):
		"""Return cube, normalized in spots by shifting pixel values."""
		quantiles = self.quantiles(quantile)
		result = np.zeros(self.cube.shape, dtype='int16')
		for n, spot in enumerate(self.spots):
			offset = level - quantiles[n]
			res = self.cube[spot].astype('int16') + offset
			res *= (res >= level) * 0.5 + 0.5 # half all values below level
			result[spot] = res
		return result.clip(0, 255).astype('uint8')

	def stretched_cube(self, quantile1=0.2, quantile2=0.2):
		"""Return cube, normalized in spots by stretching histogram."""
		quantiles1 = self.quantiles(quantile1)
		quantiles2 = self.quantiles(1.0 - quantile2)
		result = np.zeros(self.cube.shape)
		for n, spot in enumerate(self.spots):
			low, high = quantiles1[n], quantiles2[n]
			frag = self.cube[spot].astype('float64')
			res = (frag - low) * 256.0 / (high - low)
			result[spot] = res
		return result.clip(0, 255).astype('uint8')

	def occupancies(self, level):
		"""Return a dictionary of number of pixels above level in each spot."""
		return dict((n, np.count_nonzero(self.cube[spot] > level))
			for n, spot in enumerate(self.spots))

	def centers(self):
		return [tuple(map(np.mean, spot)) #(spot[0].mean(), spot[1].mean(), spot[2].mean())
			for spot in self.spots]

	def sizes_and_occupancies(self, level):
		return (
			self.assign_sizes().sizes,
			self.occupancies(level)
		)

	def as_dict(self):
		"""Return spots as a dict of (x,y,z)->spot_num."""
		spots = {}
		for n, spot in enumerate(self.spots):
			for z, y, x in izip(*spot):
				spots[x, y, z] = n
		return spots

class Images(object):
	def __init__(self, filenames=None, images=()):
		if filenames:
			images = [Image.open(f).convert('RGB') for f in filenames]
		self.images = images
		self.cubes = (None, None, None)

	def flattened(self):
		"""Return PIL image composed of all layers."""
		return reduce(ImageChops.lighter, self.images)

	def save(self, pattern):
		"""Save as series of images. In pattern {n} is for image number."""
		for n, image in enumerate(self.images):
			image.save(pattern.format(n=n))

	def assign_cubes(self, force=False):
		"""Convert images to three 3D numy arrays (by color component)."""
		if self.cubes != (None, None, None) and not force:
			return self
		assert all(image.size == self.images[0].size for image in self.images)
		im_split = [im.split() for im in self.images]
		im_shape = (len(self.images),) + tuple(reversed(self.images[0].size))
		self.cubes = [
			np.fromstring("".join(im.tostring() for im in images), 'uint8').reshape(im_shape)
			for images in zip(*im_split)
		]
		return self

	def from_cubes(self, cubes=None):
		if cubes:
			self.cubes = cubes
		assert all(cube.dtype == "uint8" for cube in self.cubes)
		assert all(cube.shape == self.cubes[0].shape for cube in self.cubes)
		im = {}
		for c, cube in enumerate(self.cubes):
			for z in range(cube.shape[0]):
				shape = tuple(reversed(cube[z].shape))[:2]
				im[c,z] = Image.fromstring("L", shape, cube[z].tostring())
		self.images = [
			Image.merge("RGB", (im[0,z], im[1,z], im[2,z]))
			for z in range(cube.shape[0])
		]
		return self

### Functions

def merge_red_green(image_red, image_green):
	"""Return PIL image composed of	`image_red`'s R values for red, ditto for G."""
	image_blue = Image.new('RGB', image_red.size)
	return Image.merge('RGB', (image_red, image_green, image_blue))

def print_sizes_and_occupancies(spots, sizes_and_occupancies):
	"""Print table with spot sizes & occupancies."""
	oses = sizes_and_occupancies
	centers = spots.centers()

	print "spot", "x", "y", "z",
	for size in sorted(oses):
		print "size" + str(size), "occupancy" + str(size),
	print

	for n in spots.ids():
		print n,
		print int(centers[n][2]), int(centers[n][1]), int(centers[n][0]),
		for size in sorted(oses):
			print oses[size][0][n], oses[size][1][n],
		print

### Helpers

def find_components(edges):
	"""Find connected components from graph defined by edges dictionary."""
	graph = dict(edges)
	components = []
	while graph != {}:
		vertex, neighbors = graph.popitem()
		component = set([vertex])
		while neighbors != []:
			vertex = neighbors.pop()
			component |= set([vertex])
			if vertex in graph:
				neighbors += graph.pop(vertex)
		components.append(component)
	return components

def xyzvrange((x0, y0, z0)):
	"""Iterate over coords of neighbors differing in exactly one coord."""
	yield x0 - 1, y0, z0
	yield x0, y0 - 1, z0
	yield x0, y0, z0 - 1
	yield x0 + 1, y0, z0
	yield x0, y0 + 1, z0
	yield x0, y0, z0 + 1

def xyzrange((x0, y0, z0), d=1):
	"""Iterate over coords in neighbourhood of point `xyz` of size `d`."""
	try:
		dx, dy, dz = d
	except Exception:
		dx = dy = dz = d
	for x in xrange(x0 - dx, x0 + dx + 1):
		for y in xrange(y0 - dy, y0 + dy + 1):
			for z in xrange(z0 - dz, z0 + dz + 1):
				yield x, y, z
