"""
This module provides Amazon Integration for the Jet Cluster.
"""

import boto3
import os
import time

from ruamel.yaml import YAML
from pprint import pprint
from cStringIO import StringIO


yaml = YAML(typ='safe')
_object = object()


class ConfigurationError(Exception):
    " Configuration issues with the cluster "


class DictMapper(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data

    def __getattr__(self, name, default=_object):
        value = self.data.get(name, default)
        if value is _object:
            raise AttributeError('no such key: %s' % name)
        if type(value) is dict:
            return DictMapper(name, value)
        else:
            return value


demo = """
version: "0.1"
cluster:
    name: demo
    namespace: .local
    tasks:
    tasksets:
"""


class Cluster(DictMapper):
    def __init__(self, filename, args=None):
        if filename.endswith('.yaml'):
            if not os.path.exists(filename):
                raise ConfigurationError(
                    "Cluster configuration file doesn't exist: %s" % filename
                )
            data = open(filename).read()
            self.filename = filename
        else:
            data = demo
            self.filename = None
        args = args or {}
        conf = yaml.load(StringIO(data % args))
        self.version = conf['version']
        self.data = conf['cluster']

    @property
    def tasks(self):
        for name, task in self.data['tasks'].items():
            yield DictMapper(name, task)

    @property
    def tasksets(self):
        for name, taskset in self.data['tasksets'].items():
            yield DictMapper(name, taskset)

    def getTask(self, name):
        value = self.data['tasks'].get(name)
        if value:
            return DictMapper(name, value)
        else:
            raise ConfigurationError("No such task: %s" % name)

    def getTaskset(self, name):
        value = self.data['tasksets'].get(name)
        if value:
            return DictMapper(name, value)
        else:
            raise ConfigurationError("No such taskset: %s" % name)


class Task(object):
    """
    A Task being run on the Cluster.
    """
    __taskDefn = None

    def __init__(self, aws, data):
        self.aws = aws
        self.data = data

    @property
    def state(self):
        return self.data['lastStatus'].lower()

    @property
    def id(self):
        return self.data['taskArn'].split('task/')[-1]

    @property
    def containerIds(self):
        return [ x['containerArn'].split('container/')[-1] for x in self.data['containers'] ]

    @property
    def name(self):
        return self.data['containers'][0]['name']
    
    @property
    def instanceId(self):
        return self.data['containerInstanceArn'].split('instance/')[-1]

    @property
    def taskDefnArn(self):
        return self.data['taskDefinitionArn']

    @property
    def container(self):
        return self.data['containers'][0]

    @property
    def instance(self):
        return self.aws.instances.get(id=self.instanceId)

    @property
    def isService(self):
        return self.data['group'].startswith('service:')

    @property
    def hostports(self):
        ports = [ b['hostPort'] for b in self.container['networkBindings'] ]
        ports.sort()
        return ports

    @property
    def taskCfg(self):
        return self.aws.cluster.getTask(self.name)

    @property
    def description(self):
        return self.taskCfg.description

    @property
    def taskDefn(self):
        if self.__taskDefn is None:
            self.__taskDefn = self.aws.getTaskDefinition(self.taskDefnArn)
        return self.__taskDefn

    @property
    def hostname(self):
        return self.taskDefn['containerDefinitions'][0]['hostname']

    @property
    def service(self):
        return self.aws.ns.getService(self.hostname or self.name)

    def refresh(self):
        resp = self.aws.ecs.describe_tasks(cluster=aws.cluster.name, tasks=[self.id])
        if resp['tasks']:
            self.data = resp['tasks'][0]

    def stop(self, reason, wait=True):
        """
        Stop this task.
        """
        if self.state == 'stopped':
            print "Task already stopped."
        elif self.state == 'pending':
            print "Task is in the process of stopping."
            if wait:
                waiter = self.aws.ecs.get_waiter('tasks_stopped')
                waiter.wait(cluster=self.aws.cluster.name, tasks=[self.id,])
                self.refresh()
        else:
            service = self.service
            if service:
                service.deregister(self)
            print "Stopping task: %s (%s)" % (self.name, self.id)
            resp = self.aws.ecs.stop_task(
                cluster=self.aws.cluster.name, 
                task=self.id, 
                reason=reason,
            )
            if wait:
                waiter = self.aws.ecs.get_waiter('tasks_stopped')
                waiter.wait(cluster=self.aws.cluster.name, tasks=[self.id,])
                self.refresh()

    def __str__(self):
        service = self.service
        return "Task: %s (%s)%s is '%s' on '%s' as %s (%s)" % (
            self.name,
            self.id,
            self.isService and " (service task)" or "",
            self.state,
            self.instance.ec2.id,
            service and service.fqdn or 'unregistered',
            self.instance.ec2.private_ip_address,
        )


class Wrapper(object):
    """
    Basic wrapper for access to dictionary data responses.
    """

    def __init__(self, data):
        self.data = data

    @property
    def id(self):
        return self.data['Id']


class ServiceDiscoveryBase(object):
    """
    Base for Service Discovery objects that are all dictionary based.
    """

    @property
    def id(self):
        return self.data['Id']

    @property
    def arn(self):
        return self.data['Arn']

    @property
    def name(self):
        return self.data['Name']

    @property
    def fqdn(self):
        return self.name + '.' + self.aws.ns.locale


class Service(ServiceDiscoveryBase):
    """
    A Service object tells us where Tasks are running and can be contacted on
    along with the port.
    """
    __full = False

    def __init__(self, aws, data):
        self.aws = aws
        self.data = data

    def get_full_details(self):
        """
        Collect the full details for this Service.
        """
        if not self.__full:
            resp = self.aws.sd.get_service(Id=self.id)
            if resp['Service']:
                self.data = resp['Service']
            self.__full = True

    def instances(self):
        """
        Return a list of registered instances of this service.
        """
        resp = self.aws.sd.list_instances(ServiceId=self.id)
        return resp['Instances']

    def destroyInstances(self):
        """
        Delete all registered instances.
        """
        for instance in self.instances():
            self.deregister(Wrapper(instance))

    def register(self, task):
        """
        Add a DNS SRV mapping for a task.
        This should be done after a task is started up.
        """
        print "Registering new service mapping: %s -> %s:%s" % (
            task.hostname, task.instance.ec2.private_ip_address, task.hostports[0],
        )
        resp = self.aws.sd.register_instance(
            ServiceId=self.id, InstanceId=task.id, 
            Attributes={
                'AWS_INSTANCE_IPV4': task.instance.ec2.private_ip_address,
                'AWS_INSTANCE_PORT': str(task.hostports[0]),
            },
        )
        return resp['OperationId']

    def deregister(self, task):
        """
        Remove a DNS SRV mapping for a task.
        This should be done prior to shutting down a task instance.
        """
        for instance in self.instances():
            if instance['Id'] == task.id:
                print "Removing Service Registry: %s -> %s" % (
                    self.fqdn, instance['Attributes']['AWS_INSTANCE_IPV4']
                )
                resp = self.aws.sd.deregister_instance(
                    ServiceId=self.id, InstanceId=task.id,
                )
                return resp['OperationId']

    def destroy(self):
        """
        Delete a Service name and any registered instances.
        """
        self.aws.ns.deleteService(self.name)


class Namespace(ServiceDiscoveryBase):
    """
    This provides the DNS like service mappings.

    When a task is started we register that task as an instance of the service
    it represents. This allows us to determine where tasks are running and on
    what ports. 

    It also means we can create multiple instances and load balance.
    """
    __services = None

    def __init__(self, aws, locale):
        self.aws = aws
        self.locale = locale
        self.__services = {}
        resp = self.aws.sd.list_namespaces(Filters=[
            {'Name': 'TYPE', 'Values': ['DNS_PRIVATE'], 'Condition': 'EQ',},
        ])
        for ns in resp['Namespaces']:
            self.data = ns
            break
        else:
            print "Failed to collect namespace."

    @property
    def filters(self):
        return [
            {'Name': 'NAMESPACE_ID', 'Values': [self.id], 'Condition': 'EQ',},
        ]

    def getService(self, name, createIfMissing=False):
        """
        Collect a specific service.
        """
        if name not in self.__services:
            resp = self.aws.sd.list_services(Filters=self.filters)
            for serv in resp['Services']:
                if serv['Name'] not in self.__services:
                    self.__services[serv['Name']] = Service(self.aws, serv)
            if createIfMissing and name not in self.__services:
                self.createService(name)
        return self.__services.get(name)

    @property
    def services(self):
        """
        Return a list of existing services.
        """
        # Refresh the list of services by requesting a dummy services
        self.getService('dummy')
        for service in self.__services.itervalues():
            yield service

    def createService(self, name, description=''):
        """
        Create a new service record.
        """
        if name in list(self.services):
            print "Service already exists."
            return
        print "Creating new Service mapping: %s" % name
        dnsconf = {
            'NamespaceId': self.id,
            'RoutingPolicy': 'MULTIVALUE',
            'DnsRecords': [{'Type': "SRV", 'TTL': 60}],
        }
        resp = self.aws.sd.create_service(
            Name=name,
            Description=description,
            DnsConfig=dnsconf,
        )
        self.__services[name] = Service(self.aws, resp['Service'])
        return self.__services[name]
    
    def deleteService(self, name):
        """
        Delete an existing service record.
        """
        serv = self.getService(name)
        if serv:
            print "Deleting Service Mapping: %s" % name
            serv.deleteInstances()
            self.aws.sd.deleteService(Id=serv.id)
            del self.__services[name]
        else:
            print "No Service Mapping: %s" % name


class EC2Instance(object):
    """
    This object represents an EC2 Instance.
    """
    data = None
    __id = __volumes = None

    def __init__(self, aws, instanceId):
        self.aws = aws
        self.__id = instanceId
        self.refresh()

    @property
    def id(self):
        return self.__id

    def refresh(self):
        response = self.aws.ec2c.describe_instances(InstanceIds=[self.id,])
        if response['Reservations'][0]['Instances']:
            self.data = response['Reservations'][0]['Instances'][0]
            print "Instance data loaded: %s" % self.id
        else:
            print "Failed to load instance data: %s" % self.id
        self.__volumes = None

    def getTagValue(self, name):
        """
        Get the value for the named tag.
        """
        name = name.lower()
        for tag in self.tags:
            if tag['Key'].lower() == name:
                return tag['Value']

    @property
    def tags(self):
        return self.data['Tags']

    @property
    def name(self):
        return self.getTagValue('Name')

    @property
    def subnet_type(self):
        return self.getTagValue('Subnet-Type')

    @property
    def state(self):
        return self.data['State']['Name']

    @property
    def isRunning(self):
        return self.state == 'running'

    @property
    def isStopped(self):
        return self.state == 'stopped'

    @property
    def instance_type(self):
        return self.data['InstanceType']
        
    @property
    def private_ip_address(self):
        """
        Return the assigned private IP address.
        """
        return self.data.get('PrivateIpAddress', '')

    @property
    def public_ip_address(self):
        """
        Return the public IP address, if one exists.
        """
        return self.data.get('PublicIpAddress', '')

    def start(self, comment=None, wait=False):
        """
        Start this instance.
        """
        if self.isStopped:
            print "Starting EC2 Instance: %s (%s)" % (self.name, self.id)
            resp = self.aws.ec2c.start_instances(InstanceIds=[self.id,])
            state = resp['StartingInstances'][0]['CurrentState']
            if wait and state['Name'] == 'pending':
                print "Waiting for instance to start..."
                waiter = self.aws.ec2c.get_waiter('instance_running')
                waiter.wait()
            self.refresh()

    def stop(self, comment=None, wait=False):
        """
        Stop this instance.
        """
        if self.isRunning:
            print "Stopping EC2 Instance: %s (%s)" % (self.name, self.id)
            resp = self.aws.ec2c.stop_instances(InstanceIds=[self.id,])
            state = resp['StoppingInstances'][0]['CurrentState']
            if wait and state['Name'] == 'stopping':
                print "Waiting for instance to stop..."
                waiter = self.aws.ec2c.get_waiter('instance_stopped')
                waiter.wait()
            self.refresh()

    @property
    def volumes(self):
        """
        Return a list of attached EBS Volumes.
        """
        if self.__volumes is None:
            self.__volumes = []
            volids = [ v['Ebs']['VolumeId'] for v in self.data['BlockDeviceMappings'] ]
            response = self.aws.ec2c.describe_volumes(VolumeIds=volids)
            for volData in response['Volumes']:
                self.__volumes.append(Volume(self.aws, volData))
        for volume in self.__volumes:
            yield volume

    def getVolume(self, Name=None, Id=None):
        for volume in self.volumes:
            if Id and volume.id == Id:
                return volume
            elif Name and volume.name == Name:
                return volume

    def getNewDevice(self):
        """
        Look for the next available /dev/sdX device.
        """
        current = ord('b')
        for volume in self.volumes:
            if volume.attachment['Device'].startswith('/dev/sd'):
                current = max(current, ord(volume.attachment['Device'][-1]))
        return "/dev/sd%s" % chr(current + 1)


class ContainerInstance(object):
    """
    An object that represents the EC2 Instance registered with a Cluster.
    """
    __ec2 = __arn = __data = None
    def __init__(self, aws, arn):
        self.aws = aws
        self.__arn = arn
        self.__id = arn.split('instance/')[-1]

    def refresh(self):
        resp = self.aws.ecs.describe_container_instances(
            cluster=self.aws.cluster.name, containerInstances=[self.__arn]
        )
        self.__data = resp['containerInstances'][0]
        if self.__ec2 is not None:
            self.__ec2.refresh()

    def onLaunchInit(self):
        """
        Called on Launch due to ECS not being available in cloud-init.
        """
        attributes = []
        for tag in self.ec2.tags:
            if tag['Key'].startswith('aws:'):
                continue
            name = 'obsidian.%s' % tag['Key'].lower()
            value = tag['Value']
            if tag['Key'] == 'Mount':
                value = ','.join([ v.split(':')[1].split('/')[-1] for v in value.split(',') ])
            attributes.append({'name': name, 'value': value, 'targetId': self.arn,})
        response = self.aws.ecs.put_attributes(
            cluster=self.aws.cluster.name, attributes=attributes,
        )
        self.refresh()
    
    @property
    def data(self):
        if self.__data is None:
            self.refresh()
        return self.__data

    @property
    def id(self):
        return self.__id

    @property
    def arn(self):
        return self.__arn

    @property
    def ec2(self):
        if self.__ec2 is None:
            self.__ec2 = EC2Instance(self.aws, self.data['ec2InstanceId'])
        return self.__ec2

    def getAttribute(self, name):
        for attr in self.data['attributes']:
            if attr['name'] == name:
                return attr.get('value')

    def setAttribute(self, name, value):
        response = self.aws.ecs.put_attributes(
            cluster=self.aws.cluster.name,
            attributes=[{'name': name, 'value': value, 'targetId': self.arn,},],
        )

    @property
    def num_tasks(self):
        return self.data['runningTasksCount']

    @property
    def private_ip_address(self):
        return self.ec2.private_ip_address

    @property
    def public_ip_address(self):
        return self.ec2.public_ip_address

    @property
    def state(self):
        return self.ec2.state['Name']


class Instances(object):
    """
    This object is an accessor to the Container and EC2 Instances.
    """
    def __init__(self, aws):
        self.aws = aws
        self.__cont_instances = []
        self.refresh()

    def refresh(self):
        " Reload instances from AWS "
        arns = [ i.arn for i in self ]
        response = self.aws.ecs.list_container_instances(cluster=self.aws.cluster.name)
        for arn in response['containerInstanceArns']:
            if arn in arns:
                arns.remove(arn)
            else:
                self.add(ContainerInstance(self.aws, arn))
        for arn in arns:
            self.delete(self.get(arn=arn))
    
    def get(self, arn=None, id=None, name=None):
        " Get instance by ARN, Id or Name "
        for instance in self:
            if arn and instance.arn == arn:
                return instance
            elif id and (instance.id == id or instance.ec2.id == id):
                return instance
            elif name and instance.ec2.name == name:
                return instance

    def add(self, instance):
        " Add an instance "
        self.__cont_instances.append(instance)

    def delete(self, instance):
        " Remove an instance "
        if instance:
            self.__cont_instances.remove(instance)

    def __iter__(self):
        " Iterate through the Container Instances "
        for instance in self.__cont_instances:
            yield instance

    @property
    def size(self):
        return sum([ 1 for i in self ])

    @property
    def sizePrivate(self):
        return sum([ 1 for i in self.iterPrivate ])

    @property
    def sizePublic(self):
        return sum([ 1 for i in self.iterPubluc ])

    @property
    def iterPrivate(self):
        " Iterate through the Container Instances on the private subnet "
        for instance in self:
            if instance.ec2.subnet_type == 'private':
                yield instance

    @property
    def iterPublic(self):
        " Iterate through the Container Instances on the public subnet "
        for instance in self:
            if instance.ec2.subnet_type == 'public':
                yield instance

    def start(self):
        " Start all instances "
        iids = []
        for instance in self:
            iids.append(instance.ec2.id)
            instance.ec2.start(wait=False)
        print "Waiting for EC2 Instances to start.."
        waiter = self.aws.ec2c.get_waiter('instance_running')
        waiter.wait(InstanceIds=iids)
        for instance in self.instances:
            if not instance.ec2.running:
                instance.ec2.reload()

    def stop(self):
        " Stop all instances "
        iids = []
        for instance in self:
            iids.append(instance.ec2.id)
            instance.ec2.stop(wait=False)
        print "Waiting for EC2 Instances to stop..."
        waiter = self.aws.ec2c.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=iids)


class RemoteCommand(object):
    """
    A Remote Command execution on multiple instances.
    """
    __invocations = None

    def __init__(self, aws, data):
        self.aws = aws
        self.data = data
        self.__invocations = {}

    @property
    def id(self):
        return self.data['CommandId']

    @property
    def instances(self):
        return self.data['InstanceIds']

    @property
    def done(self):
        for iid in self.instances:
            if iid not in self.__invocations:
                if not self.getInvocation(iid):
                    return False
        return True

    @property
    def success(self):
        if self.done:
            for inv in self.__invocations:
                if inv['Status'] != 'Success':
                    return False
            return True

    def getInvocation(self, iid):
        resp = self.aws.ssm.get_command_invocation(
            CommandId=self.id, InstanceId=iid,
        )
        if resp['Status'] not in ('Pending', 'In Progress',):
            self.__invocations[iid] = resp
            return resp


class Volume(object):
    """
    This class represents an EBS backed Volume.
    """

    def __init__(self, aws, data):
        self.aws = aws
        self.data = data

    @property
    def id(self):
        return self.data['VolumeId']

    @property
    def name(self):
        return self.getTagValue('Name')

    @property
    def tags(self):
        return self.data.get('Tags', {})

    @property
    def attachment(self):
        if self.data['Attachments']:
            return self.data['Attachments'][0]

    @property
    def persistent(self):
        return self.attachment['DeleteOnTermination'] is False

    def __repr__(self):
        return "<Volume %s:%s %s>" % (
            self.name, self.id, 
            self.attachment and "attached to %s" % self.instance.ec2.id or "not attached"
        )

    @property
    def instance(self):
        " Get the instance we are attached to "
        if self.attachment:
            return self.aws.instances.get(id=self.attachment['InstanceId'])

    def getTagValue(self, name):
        """
        Get the value for the named tag.
        """
        name = name.lower()
        for tag in self.tags:
            if tag['Key'].lower() == name:
                return tag['Value']

    def attach(self, instance):
        """
        Attach this volume to the specified instance.
        """
        if self.attachment:
            raise ValueError("Cannot attach %s already attached." % repr(self))
        response = self.aws.ec2c.attach_volume(
            Device=instance.ec2.getNewDevice(),
            InstanceId=instance.ec2.id,
            VolumeId=self.id,
        )

    def detach(self):
        """
        Remove this volume from an existing attachment.
        """
        if not self.attachment:
            raise ValueError("Volume not currently attached.")
        if not self.persistent:
            raise ValueError("Cannot detach non-persistent volumes.")
        if not self.instance.ec2.isStopped:
            raise ValueError("Stop EC2 instance before detaching volume.")
        response = self.aws.ec2c.detach_volume(
            Device=self.attachment['Device'],
            InstanceId=self.instance.ec2.id,
            VolumeId=self.id,
        )
        if response['State'] in ['detaching', 'detached']:
            return True
        elif response['State'] == 'busy':
            raise ValueError("Volume is busy.")
        else:
            return False


class AWS(object):
    """
    Cluster API for running tasks using Amazon ECS.
    """

    __session = None
    __ec2c = __ec2r = None
    __ecs = None
    __sd = None
    __ssm = None
    __r53c = None

    # Tasks running in the cluster
    __tasks = None

    ns = None
    cluster = None
    instances = None

    def __init__(self, cluster):
        """
        Constructor:
            - tasks the cluster configuration
        """
        self.cluster = cluster
        self.__tasks = {}
        self.ns = Namespace(self, self.cluster.namespace)
        self.setup()

    def setup(self):
        self.instances = Instances(self)
    #
    # Lazy property accessors
    #
    @property
    def session(self):
        if not self.__session:
            self.__session = boto3.session.Session()
        return self.__session

    @property
    def ec2c(self):
        if not self.__ec2c:
            self.__ec2c = self.session.client('ec2')
        return self.__ec2c

    @property
    def ec2r(self):
        " The EC2 Resource object "
        if not self.__ec2r:
            self.__ec2r = self.session.resource('ec2')
        return self.__ec2r

    @property
    def ecs(self):
        if not self.__ecs:
            self.__ecs = self.session.client('ecs')
        return self.__ecs

    @property
    def sd(self):
        if not self.__sd:
            self.__sd = self.session.client('servicediscovery')
        return self.__sd

    @property
    def ssm(self):
        if not self.__ssm:
            self.__ssm = self.session.client('ssm')
        return self.__ssm

    @property
    def r53c(self):
        if not self.__r53c:
            self.__r53c = self.session.client('route53')
        return self.__r53c
    #
    # Lazy properties
    #
    @property
    def tasks(self):
        for task in self.__tasks.itervalues():
            yield task

    @property
    def clusterInstances(self):
        """
        Fetch current EC2 Instances from AWS.
        """
        return self.ec2r.instances.filter(Filters=[{
            'Name': 'tag:Cluster-Name', 'Values': [self.cluster.name,],
        }])
    #
    #
    #
    def _getVolume(self, name):
        response = self.ec2c.describe_volumes(Filters=[
            {'Name': 'tag:Name', 'Values': [name,],},
            {'Name': 'tag:Cluster-Name', 'Values': [self.cluster.name,],},
        ])
        return [ Volume(self, d) for d in response['Volumes'] ]
    #
    # Helper functions
    #
    def _getTask(self, taskid):
        resp = self.ecs.describe_tasks(cluster=self.cluster.name, tasks=[taskid,])
        if resp['tasks']:
            return Task(self, resp['tasks'][0])
        else:
            print "Failed to get task: %s" % resp['failures']

    def getTaskDefinition(self, arn):
        spec = arn.split(':task-definition/')[-1]
        resp = self.ecs.describe_task_definition(taskDefinition=spec)
        return resp['taskDefinition']

    def getTask(self, taskid):
        if ':task/' in taskid:
            taskid = taskid.split(':task/')[-1]
        if taskid not in self.__tasks:
            task = self._getTask(taskid)
            if task:
                self.__tasks[taskid] = task
        return self.__tasks.get(taskid)

    def getTaskByName(self, name):
        for task in self.listTasks():
            if task.name == name:
                return task

    def delTask(self, task):
        """
        Remove a stopped task.
        """
        if task.state != 'stopped':
            print "Cannot remove, task not stopped: %s" % task
            return
        del self.__tasks[task.id]

    def listTasks(self):
        """
        List running
        """
        response = self.ecs.list_tasks(cluster=self.cluster.name)
        retList = []
        for arn in response['taskArns']:
            retList.append(self.getTask(arn))
        return retList

    def getTagValue(self, res, name):
        name = name.lower()
        for tag in res.tags:
            if tag['Key'].lower() == name:
                return tag['Value']

    def runCommand(self, instanceids, commands, comment):
        " Run a command on the specified instances "
        response = self.ssm.send_command(
            InstanceIds=instanceids, 
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': commands,},
            Comment=comment,
        )
        return RemoteCommand(self, response['Command'])

    def topological_sort(self, source):
        """
        perform topo sort on elements.

        :arg source: list of ``(name, set(names of dependancies))`` pairs
        :returns: list of names, with dependancies listed first
        """
        pending = [(name, set(deps)) for name, deps in source]        
        emitted = []
        while pending:
            next_pending = []
            next_emitted = []
            for entry in pending:
                name, deps = entry
                deps.difference_update(set((name,)), emitted)
                if deps:
                    next_pending.append(entry)
                else:
                    yield name
                    emitted.append(name) 
                    next_emitted.append(name)
            if not next_emitted:
                raise ValueError("cyclic dependancy detected: %s %r" % (name, (next_pending,)))
            pending = next_pending
            emitted = next_emitted
    #
    #
    #
    update_cmds = [
        'yum update -y',
        '/root/bin/update.sh',
        'sudo -u ec2-user /home/ec2-user/bin/update.sh',
    ]
    sync_cmds = [
        'sudo -u ec2-user /home/ec2-user/bin/update.sh',
    ]

    def update(self, instances=None):
        """
        Run a system update on all EC2 instances in the cluster.
        """
        iids = [ i.ec2.id for i in self.instances ]
        return self.runCommand(iids, self.update_cmds, 'Automated cluster update.')

    def sync(self):
        """
        Tell all private instances to sync.
        """
        iids = [ i.ec2.id for i in self.instances.iterPrivate ]
        return self.runCommand(iids, self.sync_cmds, 'One-off Instance Sync.')

    def launchInstance(self, instType='c5.xlarge', numInst=1, mounts=None,
            db=None, private=True, ramdisk=0, name=None):
        """
        Launch a new EC2 instance into the Cluster.
        """
        tags = [{'Key': 'Cluster-Name', 'Value': self.cluster.name,},]
        if mounts:
            mountVal, device = [], ord('c')
            for mount in mounts:
                mountVal.append('/dev/sd%s:%s' % (chr(device), mount))
                device += 1
            tags.append({'Key': 'Mount', 'Value': ','.join(mountVal),})
        if db:
            tags.append({'Key': 'Instance-Type', 'Value': 'database',})
            tags.append({'Key': 'Database', 'Value': db,})
        else:
            tags.append({'Key': 'Instance-Type', 'Value': 'processor',})
        if ramdisk:
            tags.append({'Key': 'Ramdisk', 'Value': str(ramdisk),})
        if private:
            subnetType = 'private'
            subnetId = 'subnet-02b1e93a93db9fca3'
            count = self.instances.sizePrivate
        else:
            subnetType = 'public'
            subnetId = 'subnet-0577ca31f80d1e2a5'
            count = self.instances.sizePublic
        tags.append({'Key': 'Subnet-Type', 'Value': subnetType,})
        if not name:
            name = 'ECS %s %s %s' % (self.cluster.name, subnetType.title(), count+1)
        tags.append({'Key': 'Name', 'Value': name,})
        response = self.ec2c.run_instances(
            InstanceType=instType,
            MaxCount=numInst,
            MinCount=numInst,
            LaunchTemplate={'LaunchTemplateName': 'JetCluster-InstanceBase',},
            SubnetId=subnetId,
            TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags,},],
        )
        if response['Instances']:
            iid = response['Instances'][0]['InstanceId']
            print "Instance launched: %s (%s)" % (name, iid)
            # The running is not enough as we need the cloud-init to finish
            # before the ecs container is available. Only then can we setup
            # the attributes.
            print "Waiting for instance to initialize..."
            waiter = self.ec2c.get_waiter('instance_status_ok')
            waiter.wait(InstanceIds=[iid,])
            self.instances.refresh()
            instance = self.instances.get(id=iid)
            instance.onLaunchInit()
            return instance

    def dumpClusterEC2Instances(self):
        """
        Dump the current EC2 Instances in the Jet-Cluster.
        """
        instances = [ (i.ec2.name, i.ec2) for i in self.instances ]
        instances.sort()
        form1 = ('-'*32, '-'*21, '-'*12, '-'*17, '-'*9, '-'*16)
        header = "+%s+%s+%s+%s+%s+%s+" % form1
        form2 = '| %-30s | %-19s | %-10s | %-15s | %-7s | %-14s |'
        print header
        print form2 % ('Name', 'Id', 'Status', 'IP Address', 'Subnet', 'Type',)
        print header
        for name, instance in instances:
            if instance.state in ('pending', 'stopping'):
                instance.refresh()
            print form2 % (
                instance.name, 
                instance.id, 
                instance.state,
                instance.private_ip_address,
                instance.subnet_type,
                instance.instance_type,
            )
        print header

    def dumpTasks(self):
        for task in self.listTasks():
            print str(task)

    def listServices(self):
        resp = self.ecs.list_services(cluster=self.cluster.name)
        retList = []
        for arn in resp['serviceArns']:
            name = arn.split('/')[-1]
            retList.append((name, arn))
        return retList

    def startTaskset(self, name):
        """
        Run all tasks in a cluster task group.
        """
        taskSet = self.cluster.getTaskset(name)
        if taskSet is None:
            raise AttributeError("no such task set: %s" % name)
        for tsname in taskSet.depends_on:
            tset = self.cluster.getTaskset(tsname)
            for name in tset.tasks:
                task = self.getTaskByName(name)
                if not task or task.state != 'running':
                    print "Taskset dependency not running: %s" % tsname
                    return
        deps = []
        for name in taskSet.tasks:
            task = self.cluster.getTask(name)
            deps.append((task.name, task.depends_on))
        for name in self.topological_sort(deps):
            self.runTask(name, taskSet, wait=True)

    def runTask(self, nameOrTask, taskset=None, wait=False):
        """
        Run a task definition from the cluster.
        """
        if isinstance(nameOrTask, basestring):
            taskdef = self.cluster.getTask(nameOrTask)
            if taskdef is None:
                raise AttributeError('no such task: %s' % nameOrTask)
        elif isinstance(nameOrTask, DictWrapper):
            taskdef = nameOrTask
        else:
            raise TypeError('call with Task or Name')
        task = self.getTaskByName(taskdef.name)
        if task:
            if task.state == 'stopped':
                self.delTask(task)
            elif task.state == 'running':
                return
            else:
                print "Waiting for previous task to stop.."
                waiter = self.ecs.get_waiter('task_stopped')
                waiter.wait(cluster=self.cluster.name, tasks=[task.id])
                self.delTask(task)
        if taskset is None:
            group = 'single'
        elif isinstance(taskset, basestring):
            group = taskset
        else:
            group = taskset.name
        self._runTask(
            taskdef.name, 
            taskdef.task_definition,
            taskdef.container_name,
            taskdef.environment.data,
            taskdef.command,
            group=group,
            count=1,
            startedBy='AWS-Cluster-Manager',
            wait=wait,
        )

    def _runTask(self, name, taskDefn, contName, taskEnv, command, group, 
            count=1, startedBy='AWS-Client-1', wait=True):
        """
        Run a task using the specified overrides.
        """
        print "Starting task: %s" % name
        task_env = []
        containerOverrides = [{
            'name': contName,
            'command': [command,],
            'environment': task_env,
        }]
        for key, val in (taskEnv or {}).items():
            task_env.append({'name': 'JETOPT_' + key.upper(), 'value': str(val),})
        response = self.ecs.run_task(
            cluster=self.cluster.name,
            taskDefinition=taskDefn,
            overrides={'containerOverrides': containerOverrides,},
            count=count,
            startedBy=startedBy,
            group=group + ':' + name,
        )
        if response['failures']:
            print "Run Task request failed..."
            pprint(response['failures'])
            return response['failures']
        else:
            task = Task(self, response['tasks'][0])
            self.__tasks[task.id] = task
            if wait and task.state == 'pending':
                waiter = self.ecs.get_waiter('tasks_running')
                waiter.wait(cluster=self.cluster.name, tasks=[task.id,])
                task.refresh()
                if task.hostports:
                    service = self.ns.getService(task.hostname)
                    if not service:
                        service = self.ns.createService(task.hostname, task.description)
                    opId = service.register(task)
                    time.sleep(1.0)
                    while True:
                        response = self.sd.get_operation(OperationId=opId)
                        if response['Operation']['Status'].lower() == 'success':
                            print "Service registered.."
                            break
                        elif response['Operation']['Status'].lower() == 'fail':
                            raise ValueError("Service registration failed.")
                        else:
                            time.sleep(1.0)
            return task

    def stopTask(self, name, reason, wait=False):
        """
        Stop a running task.
        """
        task = self.getTaskByName(name)
        if not task:
            print "Task not running: %s" % name
            return
        if task.isService:
            print "Cannot stop task, is part of a service."
            return
        return task.stop(reason, wait=wait)

    def start(self):
        """
        Start the cluster as described in the cluster.yaml

        This will only run auto_start TaskSets.
        """
        self.instances.start()
        self.setPortalIP()
        self.startTaskset('main')
        self.startTaskset('imports')

    def shutdown(self):
        """
        Stop the entire cluster and shut it down.
        """
        self.delPortalIP()
        taskids = []
        for task in self.listTasks():
            taskids.append(task.id)
            task.stop('Cluster shutdown.', wait=False)
        print "Waiting for tasks to stop..."
        waiter = self.ecs.get_waiter('tasks_stopped')
        waiter.wait(cluster=self.cluster.name, tasks=taskids)
        self.instances.stop()

    def __updatePortalIP(self, recSet, action='UPSERT'):
        """
        Update or Create the portal.jetbilling.com DNS record.
        Call this when the cluster is started.
        """
        resp = self.r53c.list_hosted_zones()
        for zone in resp['HostedZones']:
            if zone['Name'] == 'jetbilling.com.':
                break
        else:
            print "Failed to find zone."
            return
        change = {
            'Action': action,
            'ResourceRecordSet': {
                'Name': 'portal.jetbilling.com.',
                'Type': 'A',
                'TTL': 60,
                'ResourceRecords': recSet,
            },
        }
        changeBatch = {'Changes': [change,],}
        response = self.r53c.change_resource_record_sets(
            HostedZoneId=zone['Id'], ChangeBatch=changeBatch,
        )

    def setPortalIP(self):
        recSet = []
        for instance in [ i.ec2 for i in self.instances ]:
            if instance.isRunning and instance.public_ip_address:
                recSet.append({'Value': instance.public_ip_address,})
        if recSet:
            print "Adding portal DNS entry."
            self.__updatePortalIP(recSet, 'UPSERT')

    def delPortalIP(self):
        recSet = []
        for instance in [ i.ec2 for i in self.instances ]:
            if instance.isRunning and instance.public_ip_address:
                recSet.append({'Value': instance.public_ip_address,})
        if recSet:
            print "Removing portal DNS entry."
            self.__updatePortalIP(recSet, 'DELETE')

    def startService(self, name, wait=False):
        response = self.ecs.update_service(
            cluster=self.cluster.name, service=name, desiredCount=1,
        )
        print response['services']['status']
        if wait:
            waiter = self.ecs.get_waiter('services_stable')
            waiter.wait(cluster=self.cluster.name, services=[name,])

    def stopService(self, name, wait=False):
        response = self.ecs.update_service(
            cluster=self.cluster.name, service=name, desiredCount=0,
        )
        print response
        if wait:
            waiter = self.ecs.get_waiter('services_inactive')
            waiter.wait(cluster=self.cluster.name, services=[name,])


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.yaml'):
            cluster = Cluster(sys.argv[1], {'realm': 'infosat',})
        else:
            cluster = sys.argv[1]
    else:
        cluster = 'demo'
    aws = AWS(cluster=cluster)
    print "API is available as 'aws'"

