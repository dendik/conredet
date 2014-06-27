import optparse
from os.path import join
from math import sqrt
from utils import log
import numpy as np

class Spot(object):
	known = {}
	colors = set()
	overlaps = None
	coords = None
	created = False

	def __new__(cls, color, number):
		color, number = str(color), int(number)
		if (color, number) not in cls.known:
			cls.known[color, number] = object.__new__(cls, color, number)
		return cls.known[color, number]

	def __init__(self, color, number):
		if self.created:
			return
		self.created = True
		self.color = color
		self.number = number
		self.colors.add(self.color)
		self.sizes = {}
		self.occupancies = {}
		self.overlaps = set()

	def set_coords(self, coords):
		coords = tuple(map(float, coords))
		if options.verbose:
			self.assert_same_coords(coords)
		self.coords = coords
		return self

	def assert_same_coords(self, coords):
		if self.coords and self.coords != coords:
			difference = sqrt(sum((a-b) ** 2 for a, b in zip(self.coords, coords)))
			if difference > getattr(Spot, 'difference', 0):
				Spot.difference = difference
				log('coords mismatch', difference, self.coords, coords)
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

	def repr_overlaps(self, color=None):
		if color is None:
			return "; ".join(
				self.repr_overlaps(color)
				for color in sorted(self.colors)
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
			for color in sorted(self.colors)
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

def parse_stats(fd):
	for line in fd:
		line = line.strip()
		parts = line.split()
		if not line:
			color1, color2 = None, None
		elif not color1 and not color2:
			color1, color2, extension = parts
			extension = int(extension)
		elif 'spot' in parts:
			continue
		else:
			number, x, y, z, size, occupancy = parts
			spot = Spot(color1, number).set_coords((x, y, z)).set_size(extension, size)
			spot.occupancies[extension, color2] = occupancy

def parse_spots(fd):
	for line in fd:
		line = line.strip()
		parts = line.split()
		if not line:
			color1, color2 = None, None
		elif not color1 and not color2:
			color1, color2 = parts[:2]
		else:
			spot1 = Spot(color1, parts[0])
			for number in parts[1:]:
				spot2 = Spot(color2, number)
				spot1.overlaps.add(spot2)
				spot2.overlaps.add(spot1)

def mark_good():
	Spot.good = False
	for spot in Spot.known.values():
		if spot.is_cell():
			green = len(spot.overlaps_by('green'))
			blue = len(spot.overlaps_by('blue'))
			red = len(spot.overlaps_by('red'))

			if green == blue == 2:
				spot.good = True
				for spot in spot.overlaps:
					spot.good = True

def print_all():
	for (color, number), spot in sorted(Spot.known.items()):
		print spot

def print_good():
	mark_good()
	for (color, number), spot in sorted(Spot.known.items()):
		if spot.good:
			print spot

def print_good_cells(prefix):
	mark_good()
	for (color, number), spot in sorted(Spot.known.items()):
		if spot.good and spot.is_cell():
			print prefix, spot

def print_good_coords(prefix):
	mark_good()
	for (color, number), spot in sorted(Spot.known.items()):
		if spot.good and spot.is_cell():
			reds = [spot for spot in spot.overlaps if spot.color == 'red']
			if len(reds) != 2:
				continue
			a, b, c = [np.array(spot.coords) for spot in reds + [spot]]
			ab, ac = b - a, c - a
			distance = abs(ab[0] + 1j*ab[1])
			angle = np.angle(ab[0] + 1j*ab[1], ac[0] + 1j*ac[1])
			print prefix,
			print " ".join(map(str, list(ab) + [distance, angle]))

def print_with_prefix(prefix):
	print 'prefix cell_number cell_size spot_color spot_number x y z'
	for cell in Spot.known.values():
		if not cell.is_cell():
			continue
		for spot in cell.overlaps:
			print prefix, cell.number, cell.sizes[0],
			print spot.color, spot.number, " ".join(map(str, spot.coords))

def print_series(prefix):
	Spot.known = {}
	Spot.colors = set()

	with open(join(prefix, 'stats.csv')) as stats:
		parse_stats(stats)
	with open(join(prefix, 'spots.csv')) as spots:
		parse_spots(spots)

	if options.all:
		print_all()
	if options.good:
		print_good()
	if options.good_cells:
		print_good_cells(prefix)
	if options.good_coords:
		print_good_coords(prefix)
	if options.with_prefix:
		print_with_prefix(prefix)

if __name__ == "__main__":
	p = optparse.OptionParser()
	p.add_option("-g", "--good", action="store_true")
	p.add_option("-c", "--good-cells", action="store_true")
	p.add_option("--good-coords", action="store_true")
	p.add_option("-a", "--all", action="store_true")
	p.add_option("-p", "--with-prefix", action="store_true")
	p.add_option("-v", "--verbose", action="store_true")
	options, args = p.parse_args()
	for prefix in args:
		print_series(prefix)
