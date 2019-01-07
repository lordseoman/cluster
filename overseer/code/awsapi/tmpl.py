"""
This module uses YAML to present a template.
"""

import os
from ruamel.yaml import YAML
from cStringIO import StringIO

from common import DictMapper


yaml = YAML(typ='safe')
_object = object()


class Template(object):
    """

    """
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
        args = args or {}
        conf = yaml.load(StringIO(data % args))
        for name, value in conf.items():
            if isinstance(value, dict):
                setattr(self, name, DictMapper(name, value))
            else:
                setattr(self, name, value)


def loadTemplate(filename, args=None):
    return Template(filename, args=args)

