"""
This module provide Cluster Configuration
"""

import os
from ruamel.yaml import YAML
from cStringIO import StringIO

from common import DictMapper


yaml = YAML(typ='safe')
_object = object()


class ConfigurationError(Exception):
    """
    Configuration issues with the cluster 
    """


demo = """
version: "0.1"
cluster:
    name: demo
    namespace: .local
    tasks:
    tasksets:
"""


class Cluster(DictMapper):
    def __init__(self, filename, args=None):
        if filename.endswith('.yaml'):
            if not os.path.exists(filename):
                raise ConfigurationError(
                    "Cluster configuration file doesn't exist: %s" % filename
                )
            data = open(filename).read()
            self.filename = filename
        else:
            data = demo
            self.filename = None
        self.args = args or {}
        conf = yaml.load(StringIO(data))
        self.version = conf['version']
        self.data = conf['cluster']

    @property
    def tasks(self):
        for name, task in self.data['tasks'].items():
            yield DictMapper(name, task)

    @property
    def tasksets(self):
        for name, taskset in self.data['tasksets'].items():
            yield DictMapper(name, taskset)

    def getTask(self, name):
        value = self.data['tasks'].get(name)
        if value:
            return DictMapper(name, value)
        else:
            raise ConfigurationError("No such task: %s" % name)

    def getTaskset(self, name):
        value = self.data['tasksets'].get(name)
        if value:
            return DictMapper(name, value)
        else:
            raise ConfigurationError("No such taskset: %s" % name)

