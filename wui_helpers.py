class ConfigObject(object):
    def __init__(self, app):
        vars(self)['app'] = app
    def __getattr__(self, key):
        return vars(self)['app'].config[key.upper()]
    def __setattr__(self, key, value):
        vars(self)['app'].config[key.upper()] = value
