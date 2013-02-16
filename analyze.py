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
from itertools import count
from PIL import Image, ImageChops
import numpy as np

class Spots(object):
	def __init__(self, cube, level, colors=None):
		self.cube = cube
		self.level = level
		self.pixels = set()
		self.spots = []
		self.sizes = {}
		self.colors = colors or {}

	def detect_pixels(self):
		"""Return list of coordinates of pixels above level."""
		self.pixels = set(zip((self.cube > self.level).nonzero()))

	def detect_cc(self):
		"""Detect spots as connected components of intensive pixels."""
		if not self.pixels:
			self.detect_pixels()
		edges = {}
		for pixel in self.pixels:
			for other in xyzvrange(pixel):
				if other in self.pixels:
					edges.setdefault(pixel, []).append(other)
		for coords in enumerate(find_components(edges)):
			for coord in coords:
				self.spots[coord] = spot
		return self

	def detect_tight(self, neighbors, distance):
		"""Detect groups of pixels, with at least `neighbors` in `distance`"""
		if not self.pixels:
			self.detect_pixels()
		spot = iter(count(1))
		for pixel in sorted(self.pixels):
			neighborhood = [other
				for other in xyzrange(distance) if other in self.pixels]
			if len(neighborhood) > neighbors:
				spot_ids = set(self.spots[other]
					for other in neighborhood if other in self.spots)
				assert len(spot_ids) <= 1
				if not spot_ids:
					spot_ids.add(spot.next())
				self.spots[pixel] = spot_ids.pop()
		return self

	def filter_by_size(self, min_size, max_size):
		"""Remove spots not fitting in the given size range."""
		if not self.sizes:
			self.assign_sizes()
		self.spots = dict((pixel, spot)
			for pixel, spot in self.spots.iteritems()
			if min_size <= self.sizes[spot] <= max_size
		)
		return self

	def expanded(self, d=1):
		"""Return set of spots expanded by `d` pixels in each direction."""
		result = Spots(self.cube, self.level, colors=self.colors)
		for pixel in self.spots:
			for other in xyzrange(pixel, d):
				result.spots[other] = self.spots[pixel]
		return result

	def __sub__(self, other):
		"""Return set of spots minus pixels in `other` spots with same ids."""
		result = Spots(self.cube, self.level, colors=self.colors)
		for pixel in self.spots:
			if other.spots.get(pixel) == self.spots[pixel]:
				continue
			result.spots[pixel] = self.spots[pixel]
		return result

	def assign_sizes(self):
		"""Return a dictionary of spot sizes."""
		self.sizes = {}
		for pixel, spot in self.spots.iteritems():
			self.sizes[spot] = self.sizes.get(spot, 0) + 1
		return self

	def assign_few_colors(self,
			possible_colors=[(0,255,0), (0,128,0), (0,255,128), (0,128,255)]):
		"""Assign as few as possible colors to spots ."""
		self.colors = dict((spot, possible_colors[0])
			for spot in set(self.ids()))
		for next_color in possible_colors[1:]:
			for pixel in self.spots:
				for other in xyzrange(pixel, 3):
					if other in self.spots:
						s1 = self.spots[pixel]
						s2 = self.spots[other]
						if s1 != s2 and self.colors[s1] == self.colors[s2]:
							self.colors[s1] = next_color
							break
		return self

	def assign_random_colors(self, r=True, g=True, b=True):
		"""Aggign random color to each spot."""
		v = lambda: return random.randint(128, 255)
		self.colors = dict((spot, (r and v(), g and v(), b and v()))
			for spot in set(self.ids()))
		return self

	def draw_flat(self, image):
		"""Draw spots on a flat image."""
		return self.draw_3D([image] * self.cube.shape[-1])

	def draw_3D(self, images):
		"""Draw spots on a stack of images."""
		if not self.colors:
			self.assign_random_colors()
		for x, y, z in spots:	
			images[z].putpixel((x,y), colors[spots[x,y,z]])

	def ids(self):
		"""Return a list of available spot ids"""
		return self.spots.values()

	def quantiles(self, quantile, cube=None):
		"""Find quantile value for each spot in `self.quantiles`."""
		values = {}
		for pixel in self.spots:
			values.setdefault(self.spots[pixel], []).append((cube or self.cube)[pixel])
		for spot in values:
			values[spot].sort()
		quantiles = {}
		for spot in values:
			value = values[spot]
			quantiles[spot] = value[int(quantile * len(value))]
		return quantiles

	def normalized_cube(self, quantile=0.75, level=100):
		""" """
		quantiles = self.quantiles(quantile)
		result = np.zeros(self.cube.shape, dtype='uint8')
		for spot in quantile:
			offset = level - quantile[spot]
			

class Images(object):
	def __init__(self, filenames):
		self.images = Image3d([Image.open(f).convert('RGB') for f in filenames])
		self.cubes = (None, None, None)
	
	def flattened(self):
		"""Return PIL image composed of all layers."""
		return reduce(ImageChops.lighter, self.images)

	def normalized_in(self, spots, quantile, levels):
		"""Return new Images with `neighborhood` pixels around each spot normalized."""
		for i in range(3):
			quantiles = spots.quantiles(quantile, self.cubes[i])


	def assign_cubes(self):
		...

### Functions

def merge_red_green(image_red, image_green):
	"""Return PIL image composed of	`image_red`'s R values for red, ditto for G."""
	image_blue = Image.new('RGB', image_red.size)
	return Image.merge('RGB', (image_red, image_green, image_blue))

def images_to_cube(images):
	"""Convert grayscale images to a 3D numpy array."""
	assert all(image.size == images[0].size for image in images)
	assert all(image.mode == 'L' for image in images)
	a = np.fromstring("".join(im.tostring() for im in images), 'uint8')
	a.shape = image[0].size + (len(images),)
	return a

def load_all(filenames):

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

def xyzvrange(x0, y0, z0):
	"""Iterate over coords of neighbors differing in exactly one coord."""
	yield x0 - 1, y0, z0
	yield x0, y0 - 1, z0
	yield x0, y0, z0 - 1
	yield x0 + 1, y0, z0
	yield x0, y0 + 1, z0
	yield x0, y0, z0 + 1

def xyzrange((x0, y0, z0), d=1):
	"""Iterate over coords in neighbourhood of point `xyz` of size `d`."""
	for x in xrange(x0 - d, x0 + d + 1):
		for y in xrange(y0 - d, y0 + d + 1):
			for z in xrange(z0 - d, z0 + d + 1):
				yield x, y, z
