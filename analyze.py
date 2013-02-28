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
	7. G: calculate number of pixels in (extended / poked) spot
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
import sys
import random
from itertools import count
from PIL import Image, ImageChops
import numpy as np

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
		self.sizes = [] # indices gone wrong
		return self

	def expanded(self, d=1):
		"""Return set of spots expanded by `d` pixels in each direction."""
		result = Spots(self.cube, colors=self.colors)
		for n, spot in enumerate(self.spots):
			coords = set(map(tuple, np.transpose(spot).tolist()))
			for coord in set(coords):
				coords |= set(xyzrange(coord, d))
			self.spots[n] = zip(*sorted(coords))
		return result

	def __sub__(self, other):
		"""Return set of spots minus pixels in `other` spots with same ids."""
		result = Spots(self.cube, colors=self.colors)
		for spot1, spot2 in zip(self.spots, other.spots):
			spot1 = set(np.transpose(spot1).tolist())
			spot2 = set(np.transpose(spot2).tolist())
			spot3 = zip(*sorted(spot1 - spot2))
			result.spots.append(spot3)
		return result

	def assign_pixels(self, level, force=False):
		"""Detect list of coordinates of pixels above level."""
		if force or not self.pixels:
			coords = (self.cube > level).nonzero()
			self.pixels = set(zip(*coords))
		return self

	def assign_sizes(self, force=False):
		"""Return a dictionary of spot sizes."""
		if not force and self.sizes:
			return self
		self.sizes = dict((n, len(spot)) for n, spot in enumerate(self.spots))
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
		"""Aggign random color to each spot."""
		if self.colors and not force:
			return self
		v = lambda x: (x is None) and random.randint(128, 255) or x
		self.colors = dict((spot, (v(r), v(g), v(b))) for spot in set(self.ids()))
		return self

	def draw_flat(self, image):
		"""Draw spots on a flat image."""
		return self.draw_3D([image] * self.cube.shape[-1])

	def draw_3D(self, images):
		"""Draw spots on a stack of images."""
		self.assign_random_colors()
		spots = self.as_dict()
		for (x, y, z), spot in spots.iteritems():
			images[z].putpixel((x,y), self.colors[spot])

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
		"""Return cube"""
		quantiles = self.quantiles(quantile)
		result = np.zeros(self.cube.shape, dtype='uint8')
		for spot in quantiles:
			offset = level - quantiles[spot]
			result[self.spots[spot]] = self.cube[self.spots] - offset
		return result

	def occupancies(self, level):
		"""Return a dictionary of number of pixels above level in each spot."""
		return dict((n, len((self.cube[spot] > level).nonzero()))
			for n, spot in enumerate(self.spots))

	def as_dict(self):
		"""Return spots as a dict of (x,y,z)->spot_num."""
		spots = {}
		for n, spot in enumerate(self.spots):
			for z, y, x in spot.transpose().tolist():
				spots[x, y, z] = n
		return spots

class Images(object):
	def __init__(self, filenames):
		self.images = [Image.open(f).convert('RGB') for f in filenames]
		self.cubes = (None, None, None)

	def flattened(self):
		"""Return PIL image composed of all layers."""
		return reduce(ImageChops.lighter, self.images)

	def normalized_in(self, spots, quantile, levels):
		"""Return new Images with `neighborhood` pixels around each spot normalized."""
		self.assign_cubes()
		for i in range(3):
			quantiles = spots.quantiles(quantile, self.cubes[i])
			# XXX

	def assign_cubes(self, force=False):
		"""Convert images to three 3D numy arrays (by color component)."""
		if self.cubes != (None, None, None) and not force:
			return self
		assert all(image.size == self.images[0].size for image in self.images)
		im_split = [im.split() for im in self.images]
		im_shape = (len(self.images),) + self.images[0].size
		self.cubes = [
			np.fromstring("".join(im.tostring() for im in images), 'uint8').reshape(im_shape)
			for images in zip(*im_split)
		]
		return self

### Functions

def merge_red_green(image_red, image_green):
	"""Return PIL image composed of	`image_red`'s R values for red, ditto for G."""
	image_blue = Image.new('RGB', image_red.size)
	return Image.merge('RGB', (image_red, image_green, image_blue))

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

def log(*args):
	sys.stderr.write(" ".join(map(str, args)) + "\n")
