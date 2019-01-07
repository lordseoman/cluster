"""
This is a python logging handler to send log records via a PUSH socket.

This is part of the jLog service that listens on a PULL socket for log records
and then relays the logging to the Service Manager. That service then publishes
the log record.

We do this instead of a PUB/SUB socket since we want all logging to go to a
local service before being published. The jLog service runs on each node, so
you can subscriber to the local nodes jLog to get only logs for that node.
"""

import logging

import zmq
import cPickle as pickle
import socket


myip = socket.gethostbyname(socket.gethostname())


class PUSHHandler(logging.Handler):
    """
    A LogHandler that pushes log records to a local jLog service. The service
    runs on each node on port 13001.

    Identity: Node-W.X.Y.Z
    """
    def __init__(self, uri=None, socket=None, context=None):
        print "uri: %s" % uri
        logging.Handler.__init__(self)
        self.uri = uri
        self.identity = "Node-%s" % myip
        if isinstance(socket, zmq.Socket):
            self.socket = socket
            self.context = socket.context
            self.termContext = False
        else:
            self.socket = None
            self.termContext = context is None
            self.context = context or zmq.Context()
        self.backlog = []
        self.retry_limit = 10

    def connect(self):
        """
        Connect on first use.
        """
        if self.socket is None:
            self.socket = self.context.socket(zmq.PUSH)
            self.socket.identity = self.identity
            print "closed flag", self.socket.closed
        print "Connecting to %s" % self.uri
        self.socket.connect(self.uri)
        print "...connected", self.socket.closed

    def close(self):
        """
        Tidy up on close.
        """
        if self.socket and not self.socket.closed:
            self.sendBacklog()
            self.socket.close()
            self.socket = None
        if self.termContext:
            self.context.term()
        logging.Handler.close(self)

    def handleError(self, record):
        """
        Handle an error during logging.
        """
        self.backlog.append(record)

    def sendBacklog(self):
        """
        Attempt to send the backlog.
        """
        while self.backlog:
            record = self.backlog.pop(0)
            if not seld.send(record):
                self.backlog.insert(0, record)
                break

    def makePickle(self, record):
        """
        Pickles the LogRecord.
        """
        return pickle.dumps(record, 1)

    def send(self, record):
        """
        Send the record, try a couple of times.

        Note the format is (type, qualname, recordpickle).

        This allows us to filter the records without having to unpickle the
        record itself.
        """
        record.source = self.identity
        params = ['LOGRECORD', record.name, self.makePickle(record)]
        tried = 0
        while tried < self.retry_limit:
            tried += 1
            try:
                self.socket.send_multipart(params, zmq.NOBLOCK)
                return True
            except zmq.Again:
                pass
        return False

    def emit(self, record):
        """
        Emit a record.

        We pickle the whole record and send it via the PUSH socket. If the 
        socket buffer is full or fails due to connection then store the record
        in the backlog and we will try again later.
        """
        if self.socket is None:
            self.connect()
        # If connection fails socket will be None still
        if self.socket is None or not self.send(record):
            self.handleError(record)


