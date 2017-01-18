#!/usr/bin/env python
import optparse
from flask import Flask, render_template, request, send_file
from flask import redirect, url_for
from wui_helpers import ConfigObject
from wui_job import Job, Batch, all_jobs

class config(object):
	JOB_PREFIX = 'jobs'

app = Flask(__name__)
app.cfg = ConfigObject(app)
app.config.from_object('wui.config')
#app.config.from_envvar('DETECTOR_SETTINGS')

@app.route("/")
def index():
	jobs = sorted(all_jobs(app.config), key=lambda job: job.started)
	jobs = [job for job in reversed(jobs)
		if isinstance(job, Batch) and job.state != 'new']
	return render_template("index.html", jobs=jobs[:10])

@app.route("/setup", methods=["POST"])
def setup():
	job = Batch('client', request.values.get('id'), config=app.config)
	if 'image' in request.files:
		job.set_image(request.files.getlist('image'))
	if 'meta' in request.values:
		job.set_meta(request.values.to_dict())
	if 'basic' in request.values or 'start_basic' in request.values:
		job.set_basic(request.values.to_dict())
	if 'advanced' in request.values or 'start_advanced' in request.values:
		job.set(request.values.to_dict())
	if 'start_basic' in request.values or 'start_advanced' in request.values:
		job.start()
		return redirect(url_for('results', id=job.id))
	return render_template("setup.html", job=job)

@app.route("/results/<id>")
@app.route("/results/<id>/<filename>")
def results(id, filename=''):
	job = Job('client', id, config=app.config)
	if filename.endswith('.zip'):
		return send_file(job.zip(), attachment_filename=filename, as_attachment=True)
	if filename:
		path = job.results()[filename]
		return send_file(path, attachment_filename=filename, as_attachment=True)
	return render_template("results.html", job=job)

@app.route("/view/<id>/")
@app.route("/view/<id>/<filename>")
def view(id, filename=None):
	job = Job('client', id, config=app.config)
	images = [name for name in job.results() if name.endswith(".png")]
	if filename:
		assert filename.endswith(".png")
		path = job.results()[filename]
		return send_file(path)
	return render_template("view.html", job=job, images=images)

if __name__ == "__main__":
	p = optparse.OptionParser()
	p.add_option('-d', '--debug', action='store_true', default=False)
	p.add_option('-p', '--port', type=int, default=5000)
	p.add_option('-b', '--bind', help='IP address to bind', default='127.0.0.1')
	options, args = p.parse_args()

	app.run(host=options.bind, port=options.port, debug=options.debug)

# vim: set noet:
