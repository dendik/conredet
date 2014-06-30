import optparse
import results

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

def print_good_coords(prefix):
	mark_good()
	for spot in series.sorted_cells():
		if not spot.good:
			continue

		reds = [other for other in spot.overlaps if other.color == 'red']
		if len(reds) != 2:
			continue
		a, b, c = [other.center for other in reds + [spot]]
		ab, ac, bc = b - a, c - a, c - b
		distance = np.linalg.norm(ab)
		#angle = np.angle(ab[0] + 1j*ab[1], ac[0] + 1j*ac[1])
		#angle2 = np.angle(ac[0] + 1j*ac[1], bc[0] + 1j*bc[1])
		angle = acos(np.vdot(ab, ac) / np.linalg.norm(ab) / np.linalg.norm(ac))
		angle2 = acos(np.vdot(bc, ac) / np.linalg.norm(bc) / np.linalg.norm(ac))
		print prefix,
		print " ".join(map(str, list(ab) + [distance, angle, angle2])),
		print "#", spot,
		print a, b, c,
		print ab, ac

def print_with_prefix(prefix):
	print 'prefix cell_number cell_size spot_color spot_number x y z'
	for cell in series.sorted_cells:
		for spot in cell.overlaps:
			print prefix, cell.number, cell.sizes[0],
			print spot.color, spot.number, " ".join(map(str, spot.coords))

def print_series(prefix):
	series = results.Series(prefix)

	if options.all:
		print_all(series)
	if options.good:
		print_good(series)
	if options.good_cells:
		print_good_cells(series)
	if options.good_coords:
		print_good_coords(series)
	if options.with_prefix:
		print_with_prefix(series)

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
