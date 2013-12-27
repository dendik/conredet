import sys

def log(*args):
	sys.stderr.write(" ".join(map(str, args)) + "\n")
