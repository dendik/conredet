from os.path import join, exists
from utils import log, Struct
import numpy as np
import csv

verbose = False
cell_color = 'red2'
territory_color = 'red'

class Series(object):

	def __init__(self, prefix):
		self.prefix = prefix
		self.spots = {}
		self.colors = set()
		self.scale = None
		self.parse(['scale', 'signals', 'pairs',
			'stats', 'spots', 'distances'])

	def sorted_spots(self):
		return (self.spots[key] for key in sorted(self.spots))

	def sorted_cells(self):
		return (spot for spot in self.sorted_spots() if spot.is_cell())

	def spot(self, color, number):
		color, number = str(color), int(number)
		if (color, number) not in self.spots:
			self.spots[color, number] = Spot(self, color, number)
		return self.spots[color, number]

	def parse(self, names):
		for name in names:
			filename = join(self.prefix, name + '.csv')
			parser = getattr(self, 'parse_' + name)
			if exists(filename):
				with open(filename) as file:
					parser(file)

	def parse_signals(self, fd):
		for line in csv.DictReader(fd, delimiter=' '):
			v = Struct(**line)
			cell = self.spot(cell_color, v.cell_n)
			signal = self.spot(v.color, v.spot)
			signal.set_coords(map(float, [v.x, v.y, v.z]))
			signal.set_size(0, float(v.volume))
			overlap(cell, signal)

	def parse_pairs(self, fd):
		for line in csv.DictReader(fd, delimiter=' '):
			v = Struct(**line)
			spot1 = self.spot(v.color1, v.spot1)
			spot2 = self.spot(v.color2, v.spot2)
			spot1.occupancies[0, spot2.color] = float(v.overlap_volume)
			spot2.o_distances[spot1.color] = float(v.onion_distance)
			spot2.r_distances[spot1.color] = float(v.physical_distance)
			if spot2.o_distances[spot1.color] < 0:
				spot2.o_distances[spot1.color] = float('inf')
			if float(v.overlap_volume) > 0:
				overlap(spot1, spot2)
				spot2.o_distances[spot1.color] *= -1

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
				overlap(spot1, spot2)

	def parse_scale(self, fd):
		for line in csv.DictReader(fd, delimiter=' '):
			v = Struct(**line)
			self.scale = np.array(map(float, [v.x, v.y, v.z]))

	def parse_distances(self, fd):
		line = self.parse_blocks(fd)
		for color1, color2, number, o_distance, r_distance in line:
			spot1 = self.spot(color1, number)
			spot1.o_distances[color2] = float(o_distance)
			spot1.r_distances[color2] = float(r_distance)

	def mark_good(self):
		Spot.good = False
		for cell in self.sorted_cells():
			green = len(cell.overlaps_by('green'))
			blue = len(cell.overlaps_by('blue'))
			red = len(cell.overlaps_by('red'))

			if green == blue == 2:
				cell.good = True
				for cell in cell.overlaps:
					cell.good = True

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

	@property
	def cell(self):
		for spot in self.overlaps:
			if spot.is_cell():
				return spot

	def other_signal(self, pair={'green':'blue', 'blue':'green'}):
		others = self.cell.overlaps_by(pair[self.color])
		return min(others, key=self.distance)

	def is_not_broken(self):
		try:
			spot = self.other_signal()
		except Exception:
			return False
		return self.occupancies[0, spot.color] >= (min(self.size, spot.size) / 2)

	def territory_color(self):
		return territory_color

	def sum_size(self, color):
		return sum(other.sizes[0] for other in self.overlaps_by(color))

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

	def distance(self, other):
		return np.linalg.norm(self.center - other.center)

	def __repr__(self):
		return '\t'.join([
			"Spot {}_{}".format(self.color, self.number),
			"at({:6.1f}, {:6.1f}, {:4.1f})".format(*self.coords),
			self.repr_overlaps(),
			self.repr_occupancies(),
		])

def overlap(spot1, spot2):
	spot1.overlaps.add(spot2)
	spot2.overlaps.add(spot1)
