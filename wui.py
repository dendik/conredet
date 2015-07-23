from flask import Flask, render_template, request, send_file
from flask import redirect, url_for
from wui_helpers import ConfigObject
from wui_job import Job, Batch

class config(object):
	JOB_PREFIX = 'jobs'

app = Flask(__name__)
app.cfg = ConfigObject(app)
app.config.from_object('wui.config')
#app.config.from_envvar('DETECTOR_SETTINGS')

@app.route("/")
def index():
	return render_template("index.html")

@app.route("/setup", methods=["POST"])
def setup():
	job = Batch('client', request.values.get('id'), config=app.config)
	if 'image' in request.files:
		job.set_image(request.files.getlist('image'))
	if 'basic' in request.values:
		job.set_basic(request.values.to_dict())
	if 'advanced' in request.values:
		job.set(request.values.to_dict())
	if 'start' in request.values:
		job.start()
		return redirect(url_for('results', id=job.id))
	return render_template("setup.html", job=job)

@app.route("/results/<id>")
@app.route("/results/<id>/<filename>")
def results(id, filename=None):
	job = Job('client', id, config=app.config)
	if filename:
		path = job.results()[filename]
		return send_file(path, attachment_filename=filename, as_attachment=True)
	return render_template("results.html", job=job)

@app.route("/view/<id>/")
@app.route("/view/<id>/<filename>")
def view(id, filename=None):
	job = Job('client', id, config=app.config)
	if filename:
		assert filename.startswith("img-") and filename.endswith(".png")
		path = job.results()[filename]
		return send_file(path)
	return render_template("view.html", job=job)

if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0')

# vim: set noet:
