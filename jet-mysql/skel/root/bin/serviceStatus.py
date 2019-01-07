#!/usr/bin/env python
"""
Register a new service.
"""

import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv('/etc/.env')

status = sys.argv[1]
if len(sys.argv) > 2:
    message = sys.argv[2]
else:
    message = 'No message supplied.'
TaskId = os.environ.get("TASK_ID")
OverseerIP = os.environ.get('OVERSEER_IP')
params = {'Status': status, 'Message': message, 'TaskId': TaskId,}
response = requests.get('http://%s:3000/services/status' % OverseerIP, params=params)
if response.status_code == 200:
    info = response.json()
    if info['metadata']['status'] == 200:
        print "Status changed to %s" % status
    else:
        print "Failure changing status: %s" % info['metadata']['message']
else:
    print "Failed to change service status."
    print response.text

