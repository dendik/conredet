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
from scipy.ndimage.measurements import center_of_mass
from utils import log, xyzrange, xyzvrange, find_components

infinity = 10**6 # very big number, big enough to be bigger than any spot

class Spot(object):
	def __init__(self, spots, coords):
		self.spots = spots
		self.coords = coords
		self.color = (255, 255, 255)

	def size(self):
		"""Return number of pixels in the spot."""
		return len(self.coords[0])

	def mass(self, cube=None):
		"""Return sum of pixel values in the spot."""
		cube = cube or self.spots.cube
		return numpy.sum(cube[self.coords])

	def center(self):
		"""Return center of mass of the spot as a Z,Y,X tuple."""
		return tuple(map(np.mean, self.coords))

	def center_of_mass(self, cube=None):
		"""Return center of mass of the spot as a Z,Y,X tuple."""
		cube = cube or self.spots.cube
		return tuple(
			np.average(coord, weights=cube[self.coords])
			for coord in self.coords
		)

	def values(self, cube=None):
		"""Return sorted list of pixel values in the spot."""
		cube = cube or self.spots.cube
		return sorted(cube[self.coords].tolist())

	def quantile(self, quantile, cube=None):
		"""Find quantile value for the spot."""
		values = self.values(cube)
		return values[int(quantile * len(values))]

	def occupancy(self, level, cube=None):
		"""Return number of pixels above `level` in the spot."""
		cube = cube or self.spots.cube
		return np.count_nonzero(cube[self.coords] > level)

	def expanded(self, d=1, spots=None):
		"""Return a copy of the spot expanded by the given dimensions."""
		Z, Y, X = self.spots.cube.shape
		coords = set(map(tuple, np.transpose(self.coords).tolist()))
		for coord in set(coords):
			coords |= set(xyzrange(coord, d))
		coords = [(z, y, x) for z, y, x in coords
			if 0 <= z < Z and 0 <= y < Y and 0 <= x < X]
		return Spot(spots or self.spots, zip(*coords))

	def draw_3D(self, images):
		# XXX: this is the point of slowness; it must be done via numpy
		for z, y, x in set(zip(*self.coords)):
			images.images[z].putpixel((x, y), self.color)

	def __isub__(self, other):
		coords = set(zip(*self.coords)) - set(zip(*other.coords))
		self.coords = zip(*coords)
		return self

	def intersection_spots(self, spots):
		"""Return a list of spots from `spots` that intersect `self`."""
		return [spots.spots[n] for n in self.intersection_ids(spots)]

	def intersection_ids(self, spots):
		"""Return a list of ids spots from `spots` that intersect `self`."""
		spots.assign_spots_cube()
		return set(spots.spots_cube[self.coords]) - set([spots.spots_cube_null])

	def intersection_occupancy(self, spots):
		"""Return size of intersection with any spot in `spots`."""
		spots.assign_spots_cube()
		non_null = spots.spots_cube[self.coords] != spots.spots_cube_null
		return np.count_nonzero(non_null)

class Spots(object):

	def __init__(self, cube, colors=None):
		if isinstance(cube, Spots):
			vars(self).update(vars(cube))
			return
		self.cube = cube
		self.pixels = set()
		self.spots = []
		self.has_colors = False
		self.spots_cube = None

	def detect_cc(self, level):
		"""Detect spots as connected components of intensive pixels."""
		self.assign_pixels(level)
		edges = {}
		for pixel in self.pixels:
			for other in xyzvrange(pixel):
				if other in self.pixels:
					edges.setdefault(pixel, []).append(other)
		self.spots = [Spot(self, zip(*sorted(coords)))
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

	def filter_by_size(self, min_size=None, max_size=None):
		"""Remove spots not fitting in the given size range."""
		min_size = min_size or 0
		max_size = max_size or infinity
		self.spots = [spot
			for spot in self.spots
			if min_size <= spot.size() <= max_size]
		return self

	def filter_by_height(self, min_height=2, min_presence=5):
		"""Remove spots not spanning given height."""
		spots, self.spots = self.spots, []
		for spot in spots:
			zs = Counter(z for z, y, x in izip(*spot.coords))
			for z in zs:
				if zs[z] < min_presence:
					del zs[z]
			if len(zs) < min_height:
				continue
			self.spots.append(spot)
		return self

	def expanded(self, d=1):
		"""Return set of spots expanded by `d` pixels in each direction."""
		result = Spots(self.cube)
		result.spots = [spot.expanded(d, spots=result) for spot in self.spots]
		return result

	def __isub__(self, other):
		"""Return set of spots minus pixels in `other` spots with same ids."""
		for a, b in zip(self.spots, other.spots):
			a -= b
		return self

	def assign_pixels(self, level, force=False):
		"""Detect list of coordinates of pixels above level."""
		if force or not self.pixels:
			coords = (self.cube > level).nonzero()
			self.pixels = set(izip(*coords))
		return self

	def assign_few_colors(self,
			possible_colors=[(0,255,0), (0,128,0), (0,255,128), (0,128,255)],
			force=False):
		"""Assign as few as possible colors to spots ."""
		if self.has_colors and not force:
			return self
		_, W, H = self.cube.shape
		has_color = np.zeros((len(possible_colors), W, H), bool)
		for spot in self.spots:
			Z, Y, X = spot.coords
			for color in range(len(possible_colors)):
				if np.count_nonzero(has_color[color, Y, X]) == 0:
					break
			has_color[color, Y, X] = 1
			spot.color = possible_colors[color]
		self.has_colors = True
		return self

	def assign_random_colors(self, r=None, g=None, b=None, force=False):
		"""Assign random color to each spot."""
		if not self.has_colors or force:
			new = lambda: random.randint(128, 255)
			for spot in self.spots:
				spot.color = new(), new(), new()
		self.has_colors = True
		return self

	def assign_color(self, color, force=False):
		"""Assign the same color to each spot."""
		if not self.has_colors or force:
			for spot in self.spots:
				spot.color = color
		self.has_colors = True
		return self

	def assign_colors_from(self, other, force=False):
		"""Assign colors like they are in `other`."""
		if not self.has_colors or force:
			for spot, other_spot in zip(self.spots, other.spots):
				spot.color = other_spot.color
		return self

	def assign_cube(self, cube):
		"""Nice way of setting self.cube."""
		self.cube = cube
		return self

	def assign_spots_cube(self, force=False):
		"""Create `self.spots_cube`, with ids of spots in cells."""
		if force or not self.spots_cube is not None:
			self.spots_cube_null = len(self.spots) + 1
			self.spots_cube = np.zeros(self.cube.shape, dtype='uint16')
			self.spots_cube.fill(self.spots_cube_null)
			for n, spot in enumerate(self.spots):
				self.spots_cube[spot.coords] = n
		return self

	def draw_flat(self, image):
		"""Draw spots on a flat image."""
		self.draw_3D(Images(images=[image] * self.cube.shape[0]))
		return image

	def draw_3D(self, images):
		"""Draw spots on a stack of images."""
		self.assign_random_colors()
		for spot in self.spots:
			spot.draw_3D(images)
		return images

	def draw_flat_border(self, image):
		"""Draw perimeter of spots on a flat image."""
		borders = Spots(self)
		borders.spots = []
		for spot in self.spots:
			Z, Y, X = spot.coords
			Z = [0] * len(Z)
			flat = Spot(borders, (Z, Y, X))
			border = flat.expanded((0, 1, 1), borders)
			border -= flat
			borders.spots.append(border)
		borders.assign_colors_from(self, True)
		return borders.draw_flat(image)

	def normalized_cube(self, quantile=0.75, level=100):
		"""Return cube, normalized in spots by shifting pixel values."""
		result = np.zeros(self.cube.shape, dtype='int16')
		for spot in self.spots:
			offset = level - spot.quantile(quantile)
			res = self.cube[spot.coords].astype('int16') + offset
			res *= (res >= level) * 0.5 + 0.5 # half all values below level
			result[spot.coords] = res
		return result.clip(0, 255).astype('uint8')

	def stretched_cube(self, quantile1=0.2, quantile2=0.2):
		"""Return cube, normalized in spots by stretching histogram."""
		result = np.zeros(self.cube.shape)
		for spot in self.spots:
			low, high = spot.quantile(quantile1), spot.quantile(1.0 - quantile2)
			frag = self.cube[spot.coords].astype('float64')
			res = (frag - low) * 256.0 / (high - low)
			result[spot.coords] = res
		return result.clip(0, 255).astype('uint8')

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

	def clone(self):
		return Images().from_cubes([cube.copy() for cube in self.cubes])
