#!/usr/bin/env python
from PIL import Image, ImageDraw
import results
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

results.verbose = False

def all_pairs(spot):
	return [(spot1, spot2)
		for spot1 in spot.overlaps
		for spot2 in spot.overlaps
		if (spot1.color, spot2.color) == ('blue', 'green')
	]

def distance(spot1, spot2):
	x1, y1, z1 = spot1.coords
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

def is_highlightable(spot):
	if not spot.good or not spot.is_cell():
		return False
	if options.distance and max_distance(spot) < options.distance:
		return False
	return True

def highlight_series(prefix, image, image_out):
	print "Processing", prefix
	series = results.Series(prefix)
	series.mark_good()
	img = Image.open(join(prefix, image)).convert('RGB')
	draw = ImageDraw.Draw(img)
	for spot in sorted(series.spots.values()):
		if is_highlightable(spot):
			x, y, z = spot.coords
			for r in range(options.radius, options.radius + 3):
				draw.ellipse((x - r, y - r, x + r, y + r), outline=options.color)
	img.save(join(prefix, image_out))

for prefix in args:
	highlight_series(prefix, options.image, options.image_out)
