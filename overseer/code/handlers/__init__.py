"""
Handler are portions of the overseer site that are available.

The base URL is: http://overseer.<node>.<cluster>:3000/

The following handlers exist:

    - /docker/
      This provides an interface into the Docker CLI
      
    - /docker/containerPortMap.json?containerId={}
      Provides a JSON portmapping for the specified container

    - /docker/containers.html
      Present a list of existing containers

    - /jLog?qualname={}&source={}
      This provides access to a subscriber websocket to view all logs going
      through this node. Filter optionally by qualname of the handler and/or
      the source of the logs.

    - /aws/
      Proposed interface to the AWS CLI

    - /info
      Present basic info on the overseer service

    - /shutdown
      Initiate a shutdown command

    - /services?name={}
      Return a JSON list of current services

    - /services/register?name={}&containerId={}&ip={}&port={}
      Register the specified service as running.

    - /services/state?name={}&state={}&message={}
      Set the state of the specified servive.

    - /services


"""
# TODO: make this a registry

import dockerhandler
import jLog
import site
import services


def getHandlers():
    return site.getHandlers() + dockerhandler.getHandlers() + jLog.getHandlers() + services.getHandlers()

