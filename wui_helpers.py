import sys
import os

class ConfigObject(object):
  def __init__(self, app):
    vars(self)['app'] = app
  def __getattr__(self, key):
    return vars(self)['app'].config[key.upper()]
  def __setattr__(self, key, value):
    vars(self)['app'].config[key.upper()] = value

class Struct(object):
  def __getattr__(self, key):
    return vars(self).get(key)

class RedirectStd(object):
  def __init__(self, path):
    self.path = path
  def __enter__(self):
    self.fd = open(self.path, 'a')
    self.stdout = sys.stdout
    self.stderr = sys.stderr
    sys.stdout = self.fd
    sys.stderr = self.fd
  def __exit__(self, exc_type, exc_value, traceback):
    self.fd.close()
    sys.stdout = self.stdout
    sys.stderr = self.stderr

class Chdir(object):
  def __init__(self, path):
    self.path = path
  def __enter__(self):
    self.cwd = os.getcwd()
    os.chdir(self.path)
  def __exit__(self, exc_type, exc_value, traceback):
    os.chdir(self.cwd)
