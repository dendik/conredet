from flask import Flask, render_template, request
from wui_helpers import ConfigObject

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
	if 'image' in request.files:
		pass
	if 'start' in request.values:
		pass
	return render_template("setup.html")

if __name__ == "__main__":
	app.run(debug=True)

# vim: set noet:
