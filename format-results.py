import optparse
import results
import numpy as np
from math import acos

header = True
def print_header(*args):
	global header
	if header:
		print " ".join(map(str, args))
		header = False

def print_all(series):
	for spot in series.sorted_spots():
		print spot

def print_good(series):
	series.mark_good()
	for spot in series.sorted_spots():
		if spot.good:
			print spot

def print_good_cells(series):
	series.mark_good()
	for cell in series.sorted_cells():
		if cell.good:
			print series.prefix, cell

def print_good_coords(series):
	series.mark_good()
	print_header("prefix dx dy dz distance c-t1-t2-angle t1-c-t2-angle")
	for spot in series.sorted_cells():
		if not spot.good:
			continue

		reds = [other for other in spot.overlaps if other.color == 'red']
		if len(reds) != 2:
			continue
		a, b, c = [other.center for other in reds + [spot]]
		ab, ac, bc = b - a, c - a, c - b
		distance = np.linalg.norm(ab)
		angle = acos(np.vdot(ab, ac) / np.linalg.norm(ab) / np.linalg.norm(ac))
		angle2 = acos(np.vdot(bc, ac) / np.linalg.norm(bc) / np.linalg.norm(ac))
		print series.prefix,
		print " ".join(map(str, list(ab) + [distance, angle, angle2])),
		print "#", spot,
		print a, b, c,
		print ab, ac

def print_with_prefix(series):
	print_header('prefix cell_number cell_size spot_color spot_number x y z')
	for cell in series.sorted_cells:
		for spot in cell.overlaps:
			print series.prefix, cell.number, cell.sizes[0],
			print spot.color, spot.number, " ".join(map(str, spot.coords))

def print_distances(series):
	print_header('prefix cell_number spot_color territory_size o_distance r_distance')
	for spot in series.sorted_spots():
		for color2 in spot.o_distances:
			territory_size = sum((other.sizes[0] for other in spot.overlaps if other.color == color2), 0)
			print series.prefix, spot.number, spot.color, territory_size,
			print spot.o_distances[color2], spot.r_distances[color2]

def print_series(prefix):
	series = results.Series(prefix)

	for function_name, function in globals().items():
		if not function_name.startswith('print_'):
			continue
		option_name = function_name.split('print_', 1)[-1]
		if getattr(options, option_name, False):
			function(series)

if __name__ == "__main__":
	p = optparse.OptionParser()
	p.add_option("-g", "--good", action="store_true")
	p.add_option("-c", "--good-cells", action="store_true")
	p.add_option("--good-coords", action="store_true")
	p.add_option("-a", "--all", action="store_true")
	p.add_option("-p", "--with-prefix", action="store_true")
	p.add_option("--distances", action="store_true")
	p.add_option("-v", "--verbose", action="store_true")
	options, args = p.parse_args()
	for prefix in args:
		print_series(prefix)
