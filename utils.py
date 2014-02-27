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
