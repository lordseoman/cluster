This is the Cluster Management Tool.

A cluster agent container should run on each server and provides an endpoint for
docker API interaction as well as logging and events from whatever else is running
on the server in containers.

The cluster agent is the discovery service for all services running in the cluster.

A container on startup must connect to the cluster agent on the local host:

    curl http://%{GATEWAY}:3000/%{HOSTNAME}/register

The GATEWAY is the internal docker network and the HOSTNAME is the docker id.

This connects to the cluster agent and returns a JSON data response.

The response is designed to allow the container to register with the ClusterManager
(aka Overseer) and advertise the containers services, its contact IP and Port.

The cluster agent provides both a HTTP and ZMQ Request Response interface.
