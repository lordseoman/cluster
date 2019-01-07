#!/usr/bin/env python
"""
Register a new service.
"""

import requests
import os
import netifaces
import socket

serviceName = os.environ.get('SERVICE_NAME')
serviceNumber = os.environ.get('SERVICE_NUMBER')
hostname = socket.gethostname()
myip = socket.gethostbyname(hostname)

def getOverseerIP(gwip):
    response = requests.get('http://%s:3000/whatsmyip' % gwip)
    if response.status_code == 200:
        return response.json()['ip']

def getMyInfo(overseerIP):
    response = requests.get('http://%s:3000/docker/info' % overseerIP)
    if response.status_code == 200:
        return response.json()['info']

def register(overseerIP, info):
    if serviceName == 'jetdb':
        port = '3306/tcp'
    else:
        port = None
    sNumber = serviceNumber
    if not sNumber:
        sNumber = info['Config']['Labels'].get('com.docker.compose.container-number')
    portMap = info['NetworkSettings']['Ports'].get(port)
    params = {
        'ContainerId': info['ContainerId'],
        'ContainerName': info['Name'],
        'Hostname': hostname,
        'IP': myip,
        'Port': portMap and portMap[0]['HostPort'] or '',
        'ServiceName': '%s-%s' % (serviceName, sNumber),
        'TaskId': '%s-%s' % (serviceName, info['ShortId']),
    }
    response = requests.get('http://%s:3000/services/register' % overseerIP, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['metadata']['status'] == 200:
            return params
        else:
            print "Failed to register service."
            print data['metadata']['message']

def createDotEnv(overseerIP, params):
    """
    Store variables needed by serviceStatus script.
    """
    fh = open('/etc/.env', 'w')
    fh.write("TASK_ID=%s\n" % params['TaskId'])
    fh.write("OVERSEER_IP=%s\n" % overseerIP)
    fh.flush()
    fh.close()

def createProfileD(overseerIP, params):
    """
    Output variables that will add to the Environment on Login.
    """
    fh = open('/etc/profile.d/container.sh', 'w')
    fh.write("export CONTAINER_NAME=%s\n" % params['ContainerName'])
    fh.flush()
    fh.close()

def main():
    gateways = netifaces.gateways()['default']
    gwip = gateways[netifaces.AF_INET][0]
    overseerIP = getOverseerIP(gwip)
    if overseerIP:
        info = getMyInfo(overseerIP)
        if info:
            params = register(overseerIP, info)
            if params:
                print "Service registered successfully."
                createDotEnv(overseerIP, params)
                createProfileD(overseerIP, params)
        else:
            print "Failed to get docker info."
    else:
        print "Failed to get overseer IP from Gateway (%s)" % gwip

if __name__ == '__main__':
    main()

