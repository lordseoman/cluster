#!/usr/bin/env python
"""
This is a broadcaster.

We take clients sending us messages as PUSH messages and we publish those messages
to any SUBSCRIBERS that are interested.

This is the basis of the jLogger service. Each worker and service connects to a 
local broadcaster and sends its log messages. These messages are then passed on
to any clients listening. We may have a default client that listens to specific
messages and logs them to a file.
"""

import zmq


def main(timeout=500, port=13001):
    print "Starting broadcaster."
    frontend = backend = context = None
    try:
        context = zmq.Context()
        poller = zmq.Poller()
        # The frontend is a PULL/PUSH socket taking messages
        frontend = context.socket(zmq.PULL)
        frontend.bind('tcp://*:13001')
        poller.register(frontend, zmq.POLLIN)
        # The backend is a PUBLISHER sending the messages to any client listening
        backend = context.socket(zmq.PUB)
        backend.bind('tcp://*:13002')
        #
        print "Waiting for messages.."
        while True:
            try:
                events = dict(poller.poll(timeout))
            except zmq.ZMQError:
                print "We have been interrupted."
            #
            if frontend in events:
                frames = [frontend.recv(),]
                while frontend.getsockopt(zmq.RCVMORE):
                    frames.append(frontend.recv())
                print "GOT:", frames
                if frames[0] == 'SHUTDOWN':
                    print "We have been told to shutdown."
                    break
                # A properly formed message gives type, topic, msg
                elif frames[0] in ('LOGRECORD', 'MESSAGE'):
                    if len(frames) == 2:
                        frames.insert(1, 'all')
                    backend.send_multipart(frames)
                # A simple text message, then add the 'all' topic
                elif len(frames) == 1:
                    backend.send_multipart(['MESSAGE', 'all', frames[0]])
                # If the length is 2 we expect a topic, message
                elif len(frames) == 2:
                    frames.insert(0, 'MESSAGE')
                    backend.send_multipart(frames)
                else:
                    print "wierd", frames
    except KeyboardInterrupt:
        pass
    except Exception, exc:
        print exc
    finally:
        print "Exiting."
        if frontend:
            frontend.close()
        if backend:
            backend.close()
        context.term()


if __name__ == '__main__':
    main()

