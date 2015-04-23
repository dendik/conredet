from uuid import uuid4
import processor

options_blacklist = (None, 'images', 'czi_images', 'nd2_images',
	'out_signals', 'out_pairs', 'out_stats', 'out_spots', 'out_distances')

class Job(object):

	def __init__(self, id=None):
		if id is None:
			self.create(str(uuid4()))
		else:
			self.load(id)

	def create(self, id):
		self.id = id
		self.results = {} # filename -> file object / stringio
		self._set_default_options()
		self.save()

	def load(self, id):
		pass

	def save(self):
		pass

	def set_image(self, file):
		pass
		self.image_filename = file.filename
		file.save(...)
		self.save()
		pass

	def set_basic(self, options):
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
		for var in options:
			if options[var] = 'None':
				options[var] = None
			if var in self.convert:
				value = self.convert[var](var, options[var])
			self.options[var] = value
		self.save()

	def start(self):
		pass

	def done(self):
		pass # return True / False

	def _set_default_options():
		parser = processor.option_parser()
		self.options = {}
		self.convert = {}
		for option in parser.option_list:
			if not option.dest:
				continue
			if option.dest in options_blacklist:
				continue
			self.options[option.dest] = parser.defaults[option.dest]
			self.convert[option.dest] = option.convert_value
		return options
