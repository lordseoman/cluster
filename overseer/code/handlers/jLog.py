"""
This module contains the handlers for accessing the Jet Logging Service (jLog).

The Jet Logging Service runs in the jet-agent container on each node. These 
agents all proxy logging from the services running on the node to to the 
management service nodes running in the Cluster.

This module allows you to view the logs generated from this node.

Find this service at: http://overseer.<node>.jetcluster:3000/jLog

The node should be registered with the Discovery Service as <node>.<cluster>
and this nodes overseer service is available at overseer.<node>.<cluster>

As the Service Discovery contains name:port specification, the port (def 3000)
is available in the SD entry.
"""

import zmq
from tornado import web
from tornado.log import app_log
from sockjs.tornado import SockJSRouter, SockJSConnection
from zmq.eventloop.zmqstream import ZMQStream
import cPickle as pickle
import logging
import time


formatter = logging.Formatter(
    '%(asctime)s [%(source)s %(name)s %(levelname)s]: %(message)s',
    '%d/%m/%Y %H:%M:%S',
)


class ZMQSubscriber(object):
    """
    This class represents a connection to a Subscriber socket run on this 
    container. Each node holds port 13001 open for jLog entries which is then
    published on 13002 and sent on to the Management Service.

    This object is available on the SockJSRouter, which is passed to a new
    handler (the transport). 
    
    So to access this object from the Connection:

        > conn.session.server.zmq_subscriber

    """
    # List of currently listening client connections
    clients = set()

    # The stream is the ZMQ socket listening for messages
    stream = None

    # How long to keep messages in the backlog.
    backlog_mins = 60

    # The backlog.. Should be a Redis Server with timeout.
    __backlog = []

    def __init__(self, uri='tcp://127.0.0.1:13002', backlog_mins=60, topics=None):
        """
        Constructor:
        """
        self.uri = uri
        self.backlog_mins = backlog_mins
        self.topics = topics
        self.setup()

    def setup(self):
        """
        Setup the subscriber connection on first use.
        """
        app_log.info("Connecting to publisher: %s", self.uri)
        ctxt = zmq.Context()
        subscriber = ctxt.socket(zmq.SUB)
        subscriber.connect(self.uri)
        if self.topics:
            for topic in self.topics:
                subscriber.setsockopt(zmq.SUBSCRIBE, topic)
        else:
            subscriber.setsockopt(zmq.SUBSCRIBE, '')
        self.stream = ZMQStream(subscriber)
        self.stream.on_recv(self.on_recv_sub)

    def on_recv_sub(self, msg):
        """
        Called when a new message comes in from the ZMQ socket.
        """
        app_log.debug('Got a subscriber message.')
        now = time.time()
        if msg[0] == 'MESSAGE':
            text = msg[1]
        elif msg[0] == 'LOGRECORD':
            qualname = msg[1]
            record = pickle.loads(msg[2])
        self.__backlog.append(record)
        print str(record)
        # Send out the new message
        for conn in self.clients:
            conn.broadcast(self.clients, formatter.format(record))
            break
        # Now trim the backlog
        for idx, oRec in enumerate(self.__backlog):
            if (now - oRec.created) < self.backlog_mins:
                break
        if idx:
            self.__backlog = self.__backlog[idx:]

    def add(self, client):
        """
        Add a new client connection.
        """
        self.clients.add(client)

    def remove(self, client):
        """
        Remove a client connection.
        """
        self.clients.remove(client)

    def send_backlog(self, client):
        """
        Send the backlog, which is messages recieved in the last X minutes.
        """
        for msg in self.__backlog:
            client.send(formatter.format(msg))


class LoggingConnection(SockJSConnection):
    """
    Broadcast log messages to all connected clients.
    """

    def on_open(self, info):
        """
        Called when a web client connects.
        """
        app_log.info("New client has joined: %s", info.ip)
        # Adding this client to the socket means new messages are pushed
        self.session.server.zmq_subscriber.add(self)
        # Send the backlog on connection
        self.session.server.zmq_subscriber.send_backlog(self)

    def on_close(self):
        """
        Called when a web client disconnects.
        """
        app_log.info("Client has left: %s", info.ip)
        self.session.server.zmq_subscriber.remove(self)


class IndexHandler(web.RequestHandler):
    """
    Handler for rendering the viewable page showing the logger.
    """
    def get(self, *args, **kwargs):
        """
        Render the page that shows the logs on the page.
        """
        self.render('jLog.html')


def getHandlers():
    """
    Return a list of the handlers for the jLog target.
    """
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    uri = 'tcp://%s:13002' % ip
    server = SockJSRouter(LoggingConnection, '/jLog')
    server.zmq_subscriber = ZMQSubscriber(uri=uri)
    return [(r'/jLog', IndexHandler),] + server.urls

