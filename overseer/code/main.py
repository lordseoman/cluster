#!/usr/bin/env python

import zmq
from zmq.eventloop import ioloop
import sys
import os
import socket

appDir = os.path.dirname(__file__)
myip = socket.gethostbyname(socket.gethostname())

import logging
import logging.config
import loghandler

# specify new levels
logging.zmqhandlers = loghandler
logging.addLevelName(17, 'VERBOSE')
logging.addLevelName(14, 'VERYVERB')
logging.config.fileConfig(
    os.path.join(appDir, "logging.cfg"),
    defaults={
        'log_dir': os.path.join(appDir, 'logs'),
        'logstokeep': 7,
        'myip': myip,
    },
)

from tornado.log import app_log, gen_log
from tornado.web import Application
from tornado.options import define, options, parse_command_line

define('port', default=3000, help='port to listen on.')
define('debug', default=False, type=bool, help='Turns on debug logging.')
define('reload', default=False, type=bool, help='Reload application when files change.')

import handlers


def main():
    parse_command_line()
    app_log.info("Starting Overseer Application.")
    app = Application(
        handlers.getHandlers(),
        debug=options.debug,
        autoreload=options.reload,
        template_path=os.path.join(appDir, 'html'),
        static_path=os.path.join(appDir, 'static'),
    )
    app.listen(options.port)
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()

