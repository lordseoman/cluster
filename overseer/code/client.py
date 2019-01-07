#!/usr/bin/env python
"""
Simple test client to send messages to the broadcaster.
"""

import zmq
import sys


ip = sys.argv[1]
msg = sys.argv[2]

context = zmq.Context()
socket = context.socket(zmq.PUSH)
socket.identity = 'TestClient'
print "Connecting to %s" % ip
socket.connect('tcp://%s:13001' % ip)
print "Sending message...."
socket.send_multipart(['MESSAGE', msg])
print "Done"
socket.close()

