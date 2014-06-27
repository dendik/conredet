import czifile
import optparse
import os
import sys
from processor import print_czi_metadata

def print_scale(filename):
	scale = {}
	with czifile.CziFile(filename) as czi:
		for coord in "XYZ":
			scaling, = czi.metadata.findall(".//Scaling" + coord)
			scale[coord] = int(float(scaling.text) * 10**9)
	print scale['X'], scale['Y'], scale['Z'], filename

if __name__ == "__main__":
	p = optparse.OptionParser()
	p.add_option('-w', '--write', default='scale.csv')
	options, args = p.parse_args()

	for filename in args:
			print_scale(filename)

			if options.write:
				ofn = os.path.join(os.path.dirname(filename), options.write)
				with open(ofn, 'w') as fd:
					backup, sys.stdout = sys.stdout, fd
					print_scale(filename)
				sys.stdout = backup
