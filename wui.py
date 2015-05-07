from flask import Flask, render_template, request, send_file
from wui_helpers import ConfigObject
from wui_job import Job

class config(object):
	SESSIONS_DIR = 'sessions'

app = Flask(__name__)
app.cfg = ConfigObject(app)
app.config.from_object('wui.config')
#app.config.from_envvar('DETECTOR_SETTINGS')

@app.route("/")
def index():
	return render_template("index.html")

@app.route("/setup", methods=["POST"])
def setup():
	job = Job(request.values.get('id'), config=app.cfg)
	if 'image' in request.files:
		job.set_image(request.files['image'])
	if 'basic' in request.values:
		job.set_basic(request.values)
	if 'advanced' in request.values:
		job.set(request.values)
	if 'start' in request.values:
		job.start()
		return render_template("results.html", job=job)
	return render_template("setup.html", job=job)

@app.route("/results/<id>")
@app.route("/results/<id>/<filename>")
def results(id, filename=None):
	job = Job(id)
	if filename:
		file = job.results[filename]
		return send_file(file, filename=filename, as_attachment=True)
	return render_template("results.html", job=job)

if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0')

# vim: set noet:
