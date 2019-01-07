"""
Test the python.logging handler.
"""

import socket
import os

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


def main():
    """
    Run some logging.
    """
    logger = logging.getLogger('tornado.general')
    logger.info("boo")


if __name__ == '__main__':
    main()

