"""
Base site handlers.
"""

from tornado import web
import socket
import json

myip = socket.gethostbyname(socket.gethostname())


class IndexHandler(web.RequestHandler):
    """
    Landing page for the Overseer.
    """
    def get(self, *args, **kwargs):
        self.render('index.html', title="Overseer Cluster Manager")


class MyIPHandler(web.RequestHandler):
    """
    Whats My IP
    """
    def get(self):
        response = {
            'metadata': {'status': 200,},
            'ip': myip,
        }
        self.write(json.JSONEncoder().encode(response))


def getHandlers():
    return [
        (r'/whatsmyip', MyIPHandler),
        (r'/', IndexHandler),
    ]

