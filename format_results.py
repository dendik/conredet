#!/usr/bin/env python
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
			print series.label, cell

def print_good_coords(series):
	series.mark_good()
	print_header("label dx dy dz distance c-t1-t2-angle t1-c-t2-angle")
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
		print series.label,
		print " ".join(map(str, list(ab) + [distance, angle, angle2])),
		print "#", spot,
		print a, b, c,
		print ab, ac

def print_with_prefix(series):
	print_header('label cell_number cell_size spot_color spot_number x y z')
	for cell in series.sorted_cells:
		for spot in cell.overlaps:
			print series.label, cell.number, cell.sizes[0],
			print spot.color, spot.number, " ".join(map(str, spot.coords))

def print_distances(series):
	print_header('label spot_number spot_color spot_size other_color other_size spot_other_occupancy territory_color territory_size e_distance r_distance territory_occupancy')
	for spot, other in iter_good_pairs(series):
		territory_color = spot.territory_color()
		territory_size = spot.cell.sum_size(territory_color)
		print series.label, spot.number, spot.color, spot.sizes[0],
		print other.color, other.sizes[0], spot.occupancies[0, other.color],
		print territory_color, territory_size, spot.e_distances[territory_color],
		print spot.r_distances[territory_color], spot.occupancies[0, territory_color]

def print_pt_distances(series):
	print_header('label cell_number spot1_color spot1_number spot1_volume'
		' spot2_color spot2_number spot2_volume spot_distance spot_overlap'
		' territory_distance territory_overlap')
	for spot, other in iter_good_pairs(series):
		territory_color = spot.territory_color()
		print series.label, spot.cell.number,
		print spot.color, spot.number, spot.sizes[0],
		print other.color, other.number, other.sizes[0],
		print spot.distance(other), spot.occupancies[0, other.color],
		print spot.e_distances[territory_color], spot.occupancies[0, territory_color]

def print_good_pairs(series):
	print_header('label cell_number spot1_color spot1_number spot1_volume'
		' spot2_color spot2_number spot2_volume spot_distance spot_overlap')
	for spot in iter_good_spots(series):
		territory_color = spot.territory_color()
		for other in spot.cell.overlaps:
			print series.label, spot.cell.number,
			print spot.color, spot.number, spot.sizes[0],
			print other.color, other.number, other.sizes[0],
			if other.color == territory_color:
				print spot.e_distances[other], spot.occupancies[0, territory_color]
			elif spot.color == territory_color:
				print other.e_distances[spot], spot.occupancies[0, territory_color]
			else:
				print spot.r_distances[other], spot.occupancies[0, other.color]

def print_cell_distances(series):
	print_header('label cell_number b1g1 b1g2 b2g1 b2g2 b1t b2t g1t g2t')
	for cell in iter_good_cells(series):
		territory_color = cell.territory_color()
		blues = list(cell.overlaps_by('blue'))
		greens = list(cell.overlaps_by('green'))
		blues_greens = [blue.distance(green) for blue in blues for green in greens]
		territory = [spot.e_distances[territory_color] for spot in blues + greens]
		distances = " ".join(map(str, blues_greens + territory))
		distances = distances.replace('inf', '>' + str(series.scale[0] * 21))
		print series.label, cell.number, distances

def print_cell_summary(series):
	print_header('label cell_number min_D(green,blue)'
		' D(best_green,territory) D(best_blue,territory)'
		' min_D(green,territory) min_D(blue,territory)')
	for cell in iter_good_cells(series):
		territory_color = cell.territory_color()
		reds, greens, blues = (
			[spot for spot in cell.overlaps if spot.color == color]
			for color in ('red', 'green', 'blue')
		)
		best_g, best_b = min(zip(greens, blues), key=lambda (a,b): a.distance(b))
		best_rg = min(spot.e_distances[territory_color] for spot in greens)
		best_rb = min(spot.e_distances[territory_color] for spot in blues)
		print series.label, cell.number,
		print best_g.distance(best_b),
		print best_g.e_distances[territory_color], best_b.e_distances[territory_color],
		print best_rg, best_rb,
		print

def print_series(prefix, label=None):
	series = results.Series(prefix, label)

	for function_name, function in globals().items():
		if not function_name.startswith('print_'):
			continue
		option_name = function_name.split('print_', 1)[-1]
		if getattr(options, option_name, False):
			function(series)

def iter_good_spots(series):
	series.mark_good()
	for spot in series.sorted_spots():
		if spot.good:
			yield spot

def iter_good_cells(series):
	series.mark_good()
	for cell in series.sorted_cells():
		if cell.good:
			yield cell

def iter_good_pairs(series):
	series.mark_good_pairs()
	for spot in iter_good_spots(series):
		if spot.pair:
			yield spot, spot.pair

if __name__ == "__main__":
	p = optparse.OptionParser()
	p.add_option("-g", "--good", action="store_true")
	p.add_option("-c", "--good-cells", action="store_true")
	p.add_option("--good-coords", action="store_true")
	p.add_option("-a", "--all", action="store_true")
	p.add_option("-p", "--with-prefix", action="store_true")
	p.add_option("--distances", action="store_true")
	p.add_option("--pt-distances", action="store_true")
	p.add_option("--good-pairs", action="store_true")
	p.add_option("--cell-distances", action="store_true")
	p.add_option("--cell-summary", action="store_true")
	p.add_option("-v", "--verbose", action="store_true")
	options, args = p.parse_args()
	for prefix in args:
		if '=' in prefix:
			prefix, label = prefix.split('=')
			print_series(prefix, label)
		else:
			print_series(prefix)
