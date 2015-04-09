from os.path import join
from utils import log
import numpy as np

verbose = False

class Series(object):

	def __init__(self, prefix):
		self.prefix = prefix
		self.spots = {}
		self.colors = set()
		self.scale = None

		with open(join(prefix, 'scale.csv')) as scale:
			self.parse_scale(scale)
		with open(join(prefix, 'stats.csv')) as stats:
			self.parse_stats(stats)
		with open(join(prefix, 'spots.csv')) as spots:
			self.parse_spots(spots)
		with open(join(prefix, 'distances.csv')) as distances:
			self.parse_distances(distances)

	def sorted_spots(self):
		return (self.spots[key] for key in sorted(self.spots))

	def sorted_cells(self):
		return (spot for spot in self.sorted_spots() if spot.is_cell())

	def spot(self, color, number):
		color, number = str(color), int(number)
		if (color, number) not in self.spots:
			self.spots[color, number] = Spot(self, color, number)
		return self.spots[color, number]

	@staticmethod
	def parse_blocks(fd, n_headers=2):
		for line in fd:
			line = line.strip()
			parts = line.split()
			if not line:
				headers = None
			elif not headers:
				headers = parts[:n_headers]
			else:
				yield headers + parts

	def parse_stats(self, fd):
		line = self.parse_blocks(fd, 3)
		for color1, color2, extension, number, x, y, z, size, occupancy in line:
			if number == 'spot':
				continue
			extension = int(extension)
			spot = self.spot(color1, number)
			spot.set_coords((x, y, z))
			spot.set_size(extension, size)
			spot.occupancies[extension, color2] = occupancy

	def parse_spots(self, fd):
		for parts in self.parse_blocks(fd):
			(color1, color2, number), overlaps = parts[:3], parts[3:]
			spot1 = self.spot(color1, number)
			for number in overlaps:
				spot2 = self.spot(color2, number)
				spot1.overlaps.add(spot2)
				spot2.overlaps.add(spot1)

	def parse_scale(self, fd):
		for line in fd:
			self.scale = np.array(map(float, line.strip().split()[:3]))

	def parse_distances(self, fd):
		line = self.parse_blocks(fd)
		for color1, color2, number, o_distance, r_distance in line:
			spot1 = self.spot(color1, number)
			spot1.o_distances[color2] = float(o_distance)
			spot1.r_distances[color2] = float(r_distance)

	def mark_good(self):
		Spot.good = False
		for spot in self.spots.values():
			if not spot.is_cell():
				continue

			green = len(spot.overlaps_by('green'))
			blue = len(spot.overlaps_by('blue'))
			red = len(spot.overlaps_by('red'))

			if green == blue == 2:
				spot.good = True
				for spot in spot.overlaps:
					spot.good = True

class Spot(object):
	overlaps = None
	coords = None
	center = None
	created = False

	def __init__(self, series, color, number):
		if self.created:
			return
		self.series = series
		self.created = True
		self.color = color
		self.number = number
		self.series.colors.add(self.color)
		self.sizes = {}
		self.occupancies = {}
		self.overlaps = set()
		self.o_distances = {}
		self.r_distances = {}

	def set_coords(self, coords):
		self.coords = tuple(float(v) for v in coords)
		center = np.array(self.coords) * self.series.scale
		if verbose:
			self.assert_same_center(center)
		self.center = center
		return self

	def assert_same_center(self, center):
		if self.center and self.center != center:
			difference = np.linalg.norm(self.center - center)
			if difference > getattr(Spot, 'difference', 0):
				Spot.difference = difference
				log('center mismatch', difference, self.center, center)
		#assert not self.coords or self.coords == coords

	def set_size(self, extension, size):
		size = int(size)
		assert extension not in self.sizes or self.sizes[extension] == size
		self.sizes[extension] = size
		return self

	def overlaps_by(self, color):
		return set([spot for spot in self.overlaps if spot.color == color])

	def is_cell(self):
		return '2' in self.color

	def other_signal(self, pairs={'green':'blue', 'blue':'green'}):
		spot, = (spot for spot in self.overlaps if spot.color == pairs[self.color])
		return spot

	def is_not_broken(self):
		try:
			spot = self.other_signal()
		except Exception:
			return False
		return self.occupancies[0, spot.color] >= (min(self.size, spot.size) / 2)

	def repr_overlaps(self, color=None):
		if color is None:
			return "; ".join(
				self.repr_overlaps(color)
				for color in sorted(self.series.colors)
			)
		
		spots = self.overlaps_by(color)
		spot_numbers = ','.join(str(spot.number) for spot in spots)
		if spots:
			return 'overlap_{}_{}={}'.format(len(spots), color, spot_numbers)
		else:
			return 'overlap_0_{}'.format(color)

	def repr_occupancies(self, extension=None):
		if extension is None:
			return "; ".join(
				self.repr_occupancies(extension)
				for extension in self.sizes
			)

		size = "size_{}={}".format(extension, self.sizes[extension])
		occupancies = [
			"occupancy_{}_{}={}".format(extension, color, self.occupancies[extension, color])
			for color in sorted(self.series.colors)
			if (extension, color) in self.occupancies
		]
		return ",".join([size] + occupancies)

	def __repr__(self):
		return '\t'.join([
			"Spot {}_{}".format(self.color, self.number),
			"at({:6.1f}, {:6.1f}, {:4.1f})".format(*self.coords),
			self.repr_overlaps(),
			self.repr_occupancies(),
		])
