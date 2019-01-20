"""
This exposes the docker information via tornado requests.
"""

import tornado.web
import docker
import json


class DockerBase(tornado.web.RequestHandler):
    """
    Base request handler with docker basics.
    """
    def initialize(self, dockerapi):
        self.dockerapi = dockerapi

    def _get_container(self, clientIP):
        """
        Get the container sending the request.
        """
        for container in self.dockerapi.containers.list():
            for network in container.attrs['NetworkSettings']['Networks'].itervalues():
                if clientIP == network['IPAddress']:
                    return container


class DockerHandler(DockerBase):
    """
    Expose docker information.
    """
    def get(self, *args, **kwargs):
        """
        Get information from the docker agent.
        """
        return self.render(
            'containers.html', 
            title="Container List", 
            containers=self.dockerapi.containers.list()
        )


class PortMappingHandler(DockerBase):
    """
    Return the port mapping for a container.
    """
    def get(self):
        """
        Replace the Node.js discover service with portmap.
        """
        cid = self.get_argument("containerId")
        container = self.dockerapi.containers.get(cid)
        portMapping = container.attrs['NetworkSettings']['Ports']
        port = portMapping['6379/tcp'][0]['HostPort']
        cport = portMapping['16379/tcp'][0]['HostPort']
        # The host port mapping sets all requests to come from the host instead
        # of the containers IP.
        cIP = container.attrs['NetworkSettings']['Networks'].values()[0]['IPAddress']
        self.write("%s:%s@%s" % (cIP, port, cport))


class ContainerInfoHandler(DockerBase):
    """
    Return the Container Info for the requesting container.
    """
    def get(self):
        """
        """
        response = { 'metadata': {}, }
        container = self._get_container(self.request.remote_ip)
        if container:
            response = {
                'metadata': {'status': 200,},
                'info': {
                    'Name': container.name,
                    'ContainerId': container.id,
                    'ShortId': container.short_id,
                    'NetworkSettings': container.attrs['NetworkSettings'],
                    'Config': container.attrs['Config'],
                    'Logs': container.logs(),
                },
            }
        else:
            response['metadata'].update(
                {'status': 400, 'message': 'Failed to get container: %s' % self.request.remote_ip,}
            )
        self.write(json.JSONEncoder().encode(response))


def getHandlers():
    dockerapi = docker.DockerClient()
    return [
        (r'/docker/redisPortMap?', PortMappingHandler, dict(dockerapi=dockerapi)),
        (r'/docker/info', ContainerInfoHandler, dict(dockerapi=dockerapi)),
        (r'/docker/(.*)', DockerHandler, dict(dockerapi=dockerapi)),
    ]

