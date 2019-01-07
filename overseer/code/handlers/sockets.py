"""
Sockets are used to push messages from the backend to the client.

Connections:

    - LoggerConnection
      This is used to see logging messages and goes to all connected clients.
      This is a PUB/SUB socket to the jLog service.

    - EventConnection
      Listens to events on the event channel.

    - CommandConnection
      Takes input and creates a REQ job out of it. The result is returned to
      the client when it comes back.

    - BroadcastConnection
      Listens for broadcast messages that goes to all connected clients.

"""

import zmq
from tornado import web
from sockjs.tornado import SockJSRouter, SockJSConnection
from zmq.eventloop.zmqstream import ZMQStream



class ZMQSubscriber(object):
    """
    This class represents a subscriber socket connecting to a ZMQ Service.
    """
    clients = set()
    stream = None

    def __init__(self, url, topics=None):
        self.url = url
        self.topics = topics

    def setup(self):
        """
        Setup the subscriber connection on first use.
        """
        print "Connecting to publisher: %s" % self.url
        ctxt = zmq.Context()
        subscriber = ctxt.socket(zmq.SUB)
        subscriber.connect(self.url)
        if self.topics:
            for topic in self.topics:
                subscriber.setsockopt(zmq.SUBSCRIBE, topic)
        else:
            subscriber.setsockopt(zmq.SUBSCRIBE, '')
        self.stream = ZMQStream(subscriber)
        self.stream.on_recv(self.on_recv_sub)

    def add(self, client):
        """
        Add a new participant, setup on first access.
        """
        if self.stream is None:
            self.setup()
        self.clients.add(client)

    def remove(self, client):
        """
        Remove a participant, possibly disconnect when empty.
        """
        self.clients.remove(client)
        if len(self.clients) == 0:
            print "Possibly close connection."

    def on_recv_sub(self, message):
        """
        Send the message to all clients connected.
        """
        print "Got a message:", message
        for conn in self.clients:
            conn.broadcast(self.clients, message)
            break


class LoggerConnection(SockJSConnection):
    """
    Broadcast log messages to all connected clients.
    """
    subscriber = None

    def on_open(self, info):
        """
        Called when a web client connects.
        """
        print "LoggerConnection:",info
        self.subscriber.add(self)

    def on_close(self):
        """
        Called when a web client disconnects.
        """
        self.subscriber.remove(self)


class CommandConnection(SockJSConnection):
    """
    Take commands and return responses.
    """

    def on_open(self, info):
        print "CommandConnection:", info
        socket = self.context.socket(zmq.DEALER)
        socket.connect()
        self.stream = ZMQStream(socket)
        self.stream.on_recv(self.on_recv_zmq)

    def on_close(self):
        self.stream.close()

    def on_recv_zmq(self, message):
        self.send(message)


class ChatConnection(SockJSConnection):
    """
    Open a chatroom.
    """


def getsocks(logsock=None, cmdsock=None):
    """
    """
    socks = []
    if logsock:
        LoggerConnection.subscriber = ZMQSubscriber(logsock)
        socks += SockJSRouter(LoggerConnection, '/logs').urls
    return socks

