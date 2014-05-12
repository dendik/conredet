from PIL import Image, ImageDraw
import format_output
import optparse
import math
from os.path import join

p = optparse.OptionParser()
p.add_option("-r", "--radius", default=30, type=int)
p.add_option("-c", "--color", default="yellow")
p.add_option("-i", "--image", default="img-bblue.png")
p.add_option("-o", "--image-out", default="view-img-bblue.png")
p.add_option("-d", "--distance", type=float, help="min distance between paired signals")
options, args = p.parse_args()

options.verbose = False
format_output.options = options

def all_pairs(spot):
	return [(spot1, spot2)
		for spot1 in spot.overlaps
		for spot2 in spot.overlaps
		if (spot1.color, spot2.color) == ('blue', 'green')
	]

def distance(spot1, spot2):
	x1, y1, z2 = spot1.coords
	x2, y2, z2 = spot2.coords
	return math.sqrt((x1-x2)**2 + (y1-y2)**2)

def best_pairs(spot):
	pairs = sorted(all_pairs(spot), key=lambda (a, b): distance(a, b))
	pair1 = pairs.pop(0)
	pairs = [(a, b) for a, b in pairs if a != pair1[0] and b != pair1[1]]
	pair2 = pairs[0]
	return pair1, pair2

def max_distance(spot):
	distances = [distance(a, b) for a, b in best_pairs(spot)]
	return max(distances)

for prefix in args:
	print "Processing", prefix
	format_output.Spot.known = {}
	format_output.Spot.colors = set()

	with open(join(prefix, "stats.csv")) as stats:
		format_output.parse_stats(stats)
	with open(join(prefix, "spots.csv")) as spots:
		format_output.parse_spots(spots)

	img = Image.open(join(prefix, options.image)).convert('RGB')
	draw = ImageDraw.Draw(img)
	format_output.mark_good()
	for _, spot in sorted(format_output.Spot.known.items()):
		if not spot.good or not spot.is_cell():
			continue
		if options.distance and max_distance(spot) < options.distance:
			continue
		x, y, z = spot.coords
		for r in range(options.radius, options.radius + 3):
			draw.ellipse((x - r, y - r, x + r, y + r), outline=options.color)
	img.save(join(prefix, options.image_out))
