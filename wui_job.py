from uuid import uuid4
import pickle
import processor

options_blacklist = (None, 'images', 'czi_images', 'nd2_images',
	'out_signals', 'out_pairs', 'out_stats', 'out_spots', 'out_distances')

class Job(object):
	"""Image processing job.

	This object is used in these scenarios:

		1. Create empty & save: when user opens new job
		2. Load, update options, save: user edits job before run
		3. Signal start
		4. Load, update results, save: in worker process after start
		5. Load: when user receives results

	Attributes:

		* `id`: uniq id, also used as name of job folder
		* `options`: options as passed to image processor
		* `convert`: function to convert string options to respective datatypes
		* `config.job_prefix`: folder for job folders
	"""

	def __init__(self, id=None, config=None):
		self.config = config
		if id is None:
			self.create()
		else:
			self.load(id)

	def create(self):
		"""Create a new empty job with unique id."""
		self.id = str(uuid4())
		self.results = {} # filename -> file object / stringio
		self.options = {} # option_name -> option_value
		self.convert = {} # option_name -> f(name, value_str) -> option_value
		self._set_default_options()
		self.save()

	def load(self, id):
		"""Load job with a given id from storage."""
		pass

	def save(self):
		"""Save a job to storage."""
		pass

	def set_image(self, file):
		"""Set input image.

		`file`: file upload object from flask.
		"""
		pass
		self.image_filename = file.filename
		file.save(...)
		self.save()
		pass

	def set_basic(self, options):
		"""Set basic options by compiling them to processor values."""
		for color in ('red', 'green', 'blue'):
			volume = options[color + '_volume']
			self.options[color + '_detect'] = 'topvoxels({})'.format(volume)
			self.options.pop(color + '2_detect', None)
		color = options['cell_channel']
		options['wipe_radius'] = int(1.2 * int(options['cell_radius']))
		self.options[color + '2_detect'] = (
			'cylinders(n={n_cells}, radius={cell_radius}, wipe_radius={wipe_radius})'
			.format(**options)
		)
		self.save()

	def set(self, options):
		"""Update options from a dictionary. Convert values from strings."""
		for var in options:
			if options[var] = 'None':
				options[var] = None
			if var in self.convert:
				value = self.convert[var](var, options[var])
			self.options[var] = value
		self.save()

	def start(self):
		"""Signal job to be ready for processing."""
		pass

	def is_done(self):
		"""Tell if job finished."""
		pass # return True / False

	def _set_default_options():
		"""Fill in self.options from defaults used by processor."""
		parser = processor.option_parser()
		for option in parser.option_list:
			if not option.dest:
				continue
			if option.dest in options_blacklist:
				continue
			self.options[option.dest] = parser.defaults[option.dest]
			self.convert[option.dest] = option.convert_value
		return options


#from uuid import uuid4
#
#class Session(object):
#	def __init__(self, app, redis, key=None):
#		self.key = key or str(uuid4())
#		self.cfg = app.cfg
#		self.redis = redis
#
#	def set(self, key, value):
#		self.redis.hset(self.key, key, value)
#
#	def get(self, key):
#		return self.redis.hget(self.key, key)
#
#	def start(self):
#		self.redis.rpush(self.cfg.queue_key, self.key)
#
#def worker(redis, queue_key):
#	while True:
#		args = redis.blpop(queue_key)

# vim: set noet:
