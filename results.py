from os.path import join, exists
from utils import log, Struct
import numpy as np
import csv
from collections import defaultdict

verbose = False
cell_color = 'red2'
territory_color = 'red'

class Series(object):

	def __init__(self, prefix, label=None):
		self.prefix = prefix
		self.label = label or prefix
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
			overlaps = float(v.overlap_volume) > 0
			spot1 = self.spot(v.color1, v.spot1)
			spot2 = self.spot(v.color2, v.spot2)
			spot1.occupancies[0, spot2.color] = float(v.overlap_volume)
			spot1.e_distances[spot2.color] = boundary_distance(v.ellipsoid_distance, overlaps)
			spot1.r_distances[spot2] = boundary_distance(v.physical_distance)
			if overlaps:
				overlap(spot1, spot2)

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
		for color1, color2, number, o_distance, e_distance in line:
			spot1 = self.spot(color1, number)
			spot1.o_distances[color2] = float(o_distance)
			spot1.e_distances[color2] = float(e_distance)

	def mark_good(self, greens=2, blues=2):
		Spot.good = False
		for cell in self.sorted_cells():
			green = len(cell.overlaps_by('green'))
			blue = len(cell.overlaps_by('blue'))
			red = len(cell.overlaps_by('red'))

			if green == greens and blue == blues and red > 0:
				cell.good = True
				for spot in cell.overlaps:
					spot.good = True

	def mark_good_pairs(self, pair={'green':'blue', 'blue':'green'}):
		Spot.pair = Spot._pair = None
		for cell in self.sorted_cells():
			paired = [spot for spot in cell.overlaps if spot.color in pair]
			for spot in paired:
				candidates = spot.cell.overlaps_by(pair[spot.color])
				if candidates:
					spot._pair = min(candidates, key=spot.distance)
			if all(spot._pair._pair == spot for spot in paired if spot._pair):
				for spot in paired:
					spot.pair = spot._pair

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
		self.occupancies = defaultdict(float)
		self.overlaps = set()
		self.e_distances = defaultdict(lambda: float('inf')) # ellipsoid border-border
		self.o_distances = defaultdict(lambda: float('inf')) # onion border-border
		self.r_distances = defaultdict(lambda: float('inf')) # physical center-center

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

	def is_not_broken(self):
		if self.pair:
			overlap = self.occupancies[0, self.pair.color]
			half_size = min(self.size, self.pair.size) / 2
			return overlap >= half_size

	def territory_color(self):
		return territory_color

	def territory_with(self, other):
		self_territories = self.overlaps_by(self.territory_color())
		other_territories = other.overlaps_by(other.territory_color())
		best = lambda territories: max(territories, key=lambda t: t.sizes[0])
		if self_territories & other_territories:
			return best(self_territories & other_territories)
		elif self_territories and not other_territories:
			return best(self_territories)
		elif other_territories and not self_territories:
			return best(other_territories)
		else: # either no contact with territory OR signals contact different territories
			return Spot(self.series, self.territory_color(), -1).set_size(0, -1)

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

def boundary_distance(value, overlap=0):
	distance = float(value)
	if distance < 0:
		distance = float("inf")
	if overlap > 0:
		distance *= -1
	return distance
