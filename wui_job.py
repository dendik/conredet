"""Very stupid job processing.

This currently uses pickle to store data & options, folders for larger data
files, and sleep for synchronization.

May switch to Redis someday.
"""
import os
import re
from uuid import uuid4
import pickle
import time
import optparse
import processor
import results
import format_results
import traceback
from StringIO import StringIO
from zipfile import ZipFile
from wui_helpers import RedirectStd, Chdir, Struct
from utils import log

wipe_multiplier = 1.2
worker_sleep = 10 # seconds between job attempts

default_basic_options = dict(
	n_cells=150, cell_radius=30, cell_channel='red',
	red_volume=200, green_volume=200, blue_volume=200)
basic_help = dict(
	n_cells = "Expected number of cells",
	cell_radius = "Expected cell radius in pixels",
	cell_channel = "Cell channel",
	red_volume = "Expected number of voxels in red signal",
	green_volume = "Expected number of voxels in green signal",
	blue_volume = "Expected number of voxels in blue signal",
)

outfile_options = ('out_scale', 'out_signals', 'out_pairs')
options_blacklist = (None, 'images', 'czi_images', 'nd2_images',
	'out_stats', 'out_spots', 'out_distances') + outfile_options

date_re = r'\d{4}-\d{2}-\d{2}'
duration_re = r'\d(s|sec\w*|m|min\w*|h|hour|hr|d|day|w|week|month)'
treatment_re = '{date_re} {duration_re} .*'.format(**vars())
meta_options = {
	'name': r'^.*$',
	'cell_culture': r'^.+$',
	'dish_id': r'^.*$',
	'preparation_date': '^{date_re}$'.format(**vars()),
	'hybridization_date': '^{date_re}$'.format(**vars()),
	'treatment': '^$|^{treatment_re}(, {treatment_re})*$'.format(**vars()),
	'tagged_locus_1': '^.+$',
	'tagged_locus_2': '^.*$',
	'tagged_locus_3': '^.*$',
}
meta_help = {
	'name': 'Job name (folder name for files), optional. Default is {dish_id}_{last_treatment}_{tagged_locus_1}',
	'cell_culture': 'Cell culture identification, e. g.: HeLa',
	'dish_id': 'Freeform dish name before any treatment, optional. Should be the same dish for control and treated samples.',
	'preparation_date': 'Fixed cells samples preparation date, required, e. g.: 1898-08-31',
	'hybridization_date': 'Hybridization date, possibly empty, e. g.: 1898-08-31',
	'treatment': 'Treatment applied; a possibly empty comma-separated list of: date duration description, e. g.: 2015-01-01 1hour etoposide, 2015-01-01 90min reparation',
	'tagged_locus_1': 'Name of tagged locus (site, gene, territory) visible in color channel 1 (will be displayed red), e. g.: MLL1 or chr11',
	'tagged_locus_2': 'Name of tagged locus (site, gene, territory) visible in color channel 2 (will be displayed green), e. g.: MLL1 or chr11',
	'tagged_locus_3': 'Name of tagged locus (site, gene, territory) visible in color channel 3 (will be displayed blue), e. g.: MLL1 or chr11',
}

known_extensions = ('nd2', 'czi')
known_colors = ('red', 'green', 'blue')
known_roles = ('client', 'worker')
job_filename = 'job.pickle'

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
		* `state`: either of 'new', 'started', 'done'
		* `options`: options as passed to image processor
		* `help`: help messages for the options
		* `config`: application configuration dictionary, of it we use:

			* JOB_PREFIX: path to folder with job folders
	"""

	def __init__(self, role, id=None, config=None):
		assert role in known_roles
		self.role = role
		self.config = config
		if id is None:
			self.create()
		else:
			self.load(id)

	def create(self):
		"""Create a new empty job with unique id."""
		self.id = str(uuid4())
		self.state = 'new'
		self.help = dict(basic_help) # option_name -> help text
		self.options = dict(default_basic_options) # option_name -> option_value
		self.meta = {}
		self.meta_help = dict(meta_help)
		self._set_default_options()
		os.mkdir(self._filename())
		self.save()

	def load(self, id):
		"""Load job with a given id from storage.
		
		Become radioactive mutant in the process.
		(I.e. change class of self to that of the loaded job)
		"""
		self.id = id
		role = self.role
		with open(self._filename(job_filename), 'rb') as fd:
			loaded = pickle.load(fd)
			vars(self).update(vars(loaded))
		self.__class__ = loaded.__class__ # HACK: we become radioactive mutants
		self.role = role

	def save(self, set_state=None):
		"""Save a job to storage.
		
		To avoid races:

			* Client only may save job until started.
			* Client may set started flag upon saving (only once, obviously).
			* Worker only may save job between started and done.
			* Worker may set done flag upon saving (only once, obviously).
		"""
		if self.role == 'client':
			assert self.state == 'new'
		if self.role == 'worker':
			assert self.state == 'started'
		if set_state:
			self.state = set_state
		with open(self._filename(job_filename), 'wb') as fd:
			pickle.dump(self, fd)

	def _filename(self, file=None):
		"""Return filename for either job folder or a file in job folder."""
		parts = [self.config['JOB_PREFIX'], self.id]
		if file:
			parts.append(file)
		return os.path.join(*parts)

	def set_image(self, file):
		"""Set input image. Remove any previously uploaded image files.

		`file`: file upload object from flask.

		`file.filename` comes from user. Only use it to select between known
		file extensions.
		"""
		for extension in known_extensions:
			option = extension + '_images'
			filename = 'input.' + extension
			if self.options.get(option):
				self.options[option] = None
				os.remove(self._filename(filename))
			if file.filename.endswith('.' + extension):
				self.options[option] = filename # this will run with chdir
				file.save(self._filename(filename))
				self.image_filename = file.filename # for ui goodness
		self.save()

	def set_basic(self, options):
		"""Set basic options by compiling them to processor values.
		
		Since options come from user and will be pickled, take extra care
		to sanitize them.
		"""
		self._save_basic_options(options)
		for color in known_colors:
			volume = self.options[color + '_volume']
			self.options[color + '_detect'] = 'topvoxels({})'.format(volume)
			self.options.pop(color + '2_detect', None)
			self.options[color + '_role'] = 'signal'
		self._set_basic_cell_channel(self.options['cell_channel'])
		self.save()

	def _save_basic_options(self, options):
		"""Check basic options from web and save to self.options"""
		for option in list(options):
			if option not in default_basic_options:
				del options[option]
				continue
			if option == 'cell_channel':
				assert options[option] in known_colors
			else:
				options[option] = int(options[option])
		self.options.update(options)

	def _set_basic_cell_channel(self, color):
		"""Assign advanced options from basic cell* options."""
		assert color in known_colors
		radius = int(self.options['cell_radius'])
		self.options[color + '_role'] = 'territory'
		self.options[color + '2_role'] = 'core'
		self.options[color + '2_max_size'] = 0
		self.options[color + '2_min_size'] = 0
		self.options[color + '2_detect'] = (
			'cylinders(n={n_cells}, radius={cell_radius}, wipe_radius={wipe})'
			.format(wipe=int(wipe_multiplier * radius), **self.options)
		)

	def set(self, options):
		"""Update options from a dictionary. Convert values from strings.
		
		`options` come from user. Sanitize it thoroughly.
		"""
		# XXX does convert from optparse suffy as sanitizer?
		for var in options:
			if options[var] == 'None':
				options[var] = None
			if var in options_blacklist:
				continue
			if var not in self.options:
				continue
			self.options[var] = self._convert(var, options[var])
		self.save()

	def _convert(self, option_name, value):
		"""Use optionparser's convert to convert an option."""
		# XXX isn't this a shitty sanitizer?
		parser = processor.option_parser()
		for option in parser.option_list:
			if option.dest == option_name:
				convert = option.convert_value
				return convert(option_name, value)
		return str(value)

	def set_meta(self, options):
		"""Set metadata from options."""
		for var in options:
			value = options[var].strip()
			if var not in meta_options:
				continue
			self.meta[var] = value
		self.meta['name'] = self.meta.get('name') or self.name()
		self.save()

	def meta_ok(self, variable):
		"""Tell if a given variable in metadata is well-formed."""
		option_re = meta_options.get(variable, '^$')
		value = self.meta.get(variable, '')
		return bool(re.match(option_re, value))

	def name(self):
		"""Return job name."""
		if self.meta.get('name'):
			return self.meta['name']
		dish_id = self.meta.get('dish_id', '')
		treatments = self.meta.get('treatment', '').split(', ') or ['control']
		tagged_locus_1 = self.meta.get('tagged_locus_1', '')
		parts = filter(None, (dish_id, treatments[-1], tagged_locus_1))
		name = '_'.join(parts)
		name = re.sub(r'\s+', '_', name)
		name = ''.join(re.findall(r'[A-Za-z0-9_-]+', name))
		return name.lower()

	def start(self):
		"""Signal job to be ready for processing."""
		self._set_path_options()
		self.save(set_state='started')

	def is_done(self):
		"""Tell if job finished."""
		return self.state == 'done'

	def run(self):
		"""Do the job. Set state to done at the end."""
		# This is a wrapper around self._run_processor()
		# It forks, redirects stdio, changes directory to job
		# (XXX chdir(job) is a hack)
		with RedirectStd(self._filename('log.txt')):
			try:
				with Chdir(self._filename()):
					self._run()
			except Exception, e:
				log("Job failed:", e)
				log(traceback.format_exc())
				self.error = e
				self.save(set_state='error')
			else:
				self.save(set_state='done')

	def _run(self):
		"""Assuming the environment is setup, run job steps."""
		log("Starting...")
		self._run_processor()
		self._run_postprocessing()
		self._save_meta()
		log("Done!")

	def _run_processor(self):
		"""Run the required function from processor to run the jub."""
		options = Struct()
		vars(options).update(self.options)
		processor.parse_tuple_options(options)
		processor.split_color_options(options)
		processor.parse_color_list_options(options)
		processor.options = options
		processor.start()

	def _run_postprocessing(self):
		"""Generate useful aggregate tables."""
		# we are in Chdir(), hence no self._filename() stuff
		# This is bad since series names end up in the csv tables
		log("Postprocessing...")
		series = results.Series('.')
		with RedirectStd('pt_distances.csv'):
			format_results.print_pt_distances(series)

	def _save_meta(self):
		"""Save metadata in a convenient tabular format or two."""
		# we are in Chdir(), hence no self._filename() stuff
		log("Saving metadata...")
		options = list(meta_options)
		with open("meta.csv", "w") as fd:
			fd.write("\t".join(options) + "\n")
			fd.write("\t".join(self.meta.get(var, '') for var in options) + "\n")
		with open("meta.txt", "w") as fd:
			for var in options:
				fd.write("{}: {}\n".format(var, self.meta.get(var, '-')))

	def logfile(self):
		"""Return lines of the logfile for the job."""
		try:
			with open(self._filename('log.txt')) as fd:
				return list(fd)
		except Exception:
			return ['...']

	def results(self, sep=None):
		"""Return a dictionary of filenames of all downloadable file objects.
		
		key: filename, value: path.
		"""
		results = {}
		for filename in os.listdir(self._filename()):
			if filename.endswith('.pickle'):
				continue
			results[filename] = self._filename(filename)
		return results

	def zip(self):
		"""Return a zip file with all results."""
		result = StringIO()
		with ZipFile(result, 'w') as zipfile:
			results = self.results(sep='/')
			for filename in results:
				if 'input' not in filename:
					zipfile.write(results[filename], self.name() + '/' + filename)
		result.seek(0)
		return result

	def _set_path_options(self):
		"""Set options related to paths."""
		for option in outfile_options:
			filename = option.split('_')[-1] + '.csv'
			self.options[option] = filename

	def _set_default_options(self):
		"""Fill in self.options from defaults used by processor."""
		parser = processor.option_parser()
		for option in parser.option_list:
			if not option.dest:
				continue
			if option.dest in options_blacklist:
				self.options[option.dest] = None
				self.help[option.dest] = None
				continue
			self.options[option.dest] = parser.defaults[option.dest]
			self.help[option.dest] = option.help

class Batch(Job):

	def create(self):
		self.job_ids = []
		Job.create(self)

	def set_image(self, files):
		"""Create a new job for each image file uploaded."""
		assert not self.job_ids
		assert files
		for file in files:
			job = Job(self.role, config=self.config)
			job.set_image(file)
			job.save()
			self.job_ids.append(job.id)
		assert self.job_ids
		assert len(self.job_ids) == len(files)
		self.save()
		assert self.job_ids

	def start(self):
		"""Within ui. Configure each subjob. Set each subjob started."""
		assert self.job_ids
		Job.start(self)
		for job in self.jobs():
			for var in self.options:
				if var in options_blacklist:
					continue
				job.options[var] = self.options[var]
			job.meta = dict(self.meta)
			job.save(set_state='started')

	def run(self):
		"""Within worker. If all jobs are done, we are done too."""
		for job in self.jobs():
			if job.state == 'started':
				return
		for job in self.jobs():
			if job.state == 'error':
				self.save(set_state='error')
				return
		self.save(set_state='done')

	def jobs(self):
		"""Iterate all jobs within batch."""
		for id in self.job_ids:
			yield Job(self.role, id=id, config=self.config)

	def results(self, sep='-'):
		"""Within ui. Return all files of all jobs."""
		results = {}
		for job in self.jobs():
			job_results = job.results()
			for filename in job_results:
				results[job.id + sep + filename] = job_results[filename]
		return results

def worker(config):
	"""Very stupid job processing without redis."""
	while True:
		time.sleep(worker_sleep)
		for job in all_jobs(config):
			if job.state == 'started':
				log("Starting job", job.id)
				job.run()

def all_jobs(config):
	"""Return a list of all available jobs."""
	for id in os.listdir(config['JOB_PREFIX']):
		try:
			yield Job('worker', id, config=config)
		except Exception, e:
			log("Job", id, "not loaded:", e)
			continue

def run_one(prefix, id):
	job = Job('worker', id, config=dict(JOB_PREFIX=prefix))
	assert job.state != 'started'
	job.state = 'started'
	job.run()

def restart_jobs(config, ids):
	for job in all_jobs(config):
		if job.id in ids:
			job.state = 'started' # XXX we bypass checks in job.save()
			job.save()

if __name__ == "__main__":
	parser = optparse.OptionParser()
	parser.add_option('-j', '--job-prefix', help='Path to job folders')
	parser.add_option('-r', '--run', help='Run one job and quit')
	parser.add_option('-R', '--restart', action='store_true',
		help='Reset the named jobs to "new" state')
	options, args = parser.parse_args()
	if options.run:
		run_one(*os.path.split(options.run))
	elif options.restart:
		restart_jobs(dict(JOB_PREFIX=options.job_prefix), args)
	else:
		worker(dict(JOB_PREFIX=options.job_prefix))

# vim: set noet:
