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
