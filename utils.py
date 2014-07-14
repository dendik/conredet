import re
import sys
import time
import functools

def log(*args):
	sys.stderr.write(" ".join(map(str, args)) + "\n")

def logging(message):
	def decorator(f):
		@functools.wraps(f)
		def result(*args, **kws):
			log(time.strftime("%T"), message)
			return f(*args, **kws)
		return result

	if isinstance(message, str) or isinstance(message, unicode):
		return decorator
	else:
		f, message = message, (message.__name__ + "...")
		return decorator(f)

def roundint(value):
	return int(value + 0.5)

class Re(object):
	had_match = False
	def __init__(self, text):
		self.text = text
	def __call__(self, expr):
		self.match = re.search(expr, self.text)
		self.had_match = self.had_match or self.match
		return self.match
	def get(self, group=1, func=(lambda x: x), default=None):
		return func(self.match.group(group) or default)
	def __getitem__(self, arg):
		return self.get(*arg)

class Substitute(object):
	"""With-block with `object`.`attr` temporarily replaced by `value`."""
	def __init__(self, object, attr, value):
		self.object = object
		self.attr = attr
		self.value = value
	def __enter__(self):
		self.backup = getattr(self.object, self.attr)
		setattr(self.object, self.attr, self.value)
	def __exit__(self, e_type, e_value, e_tb):
		setattr(self.object, self.attr, self.backup)

def xyzvrange((x0, y0, z0)):
	"""Iterate over coords of neighbors differing in exactly one coord."""
	yield x0 - 1, y0, z0
	yield x0, y0 - 1, z0
	yield x0, y0, z0 - 1
	yield x0 + 1, y0, z0
	yield x0, y0 + 1, z0
	yield x0, y0, z0 + 1

def xyzrange((x0, y0, z0), d=1):
	"""Iterate over coords in neighbourhood of point `xyz` of size `d`."""
	try:
		dx, dy, dz = d
	except Exception:
		dx = dy = dz = d
	for x in xrange(x0 - dx, x0 + dx + 1):
		for y in xrange(y0 - dy, y0 + dy + 1):
			for z in xrange(z0 - dz, z0 + dz + 1):
				yield x, y, z

def find_components(edges):
	"""Find connected components from graph defined by edges dictionary."""
	graph = dict(edges)
	components = []
	while graph != {}:
		vertex, neighbors = graph.popitem()
		component = set([vertex])
		while neighbors != []:
			vertex = neighbors.pop()
			component |= set([vertex])
			if vertex in graph:
				neighbors += graph.pop(vertex)
		components.append(component)
	return components
