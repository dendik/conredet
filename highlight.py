from PIL import Image, ImageDraw
import format_output
import optparse
from os.path import join

p = optparse.OptionParser()
p.add_option("-r", "--radius", default=20, type=int)
p.add_option("-c", "--color", default="yellow")
p.add_option("-i", "--image", default="img-bblue.png")
p.add_option("-o", "--image-out", default="view-img-bblue.png")
options, args = p.parse_args()

options.verbose = False
format_output.options = options

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
		x, y, z = spot.coords
		for r in range(options.radius, options.radius + 3):
			draw.ellipse((x - r, y - r, x + r, y + r), outline=options.color)
	img.save(join(prefix, options.image_out))
