"""
The services handler allows service registration and discovery.

Notation:
  - Task: is a discrete docker container running on any Node and is unique.
  - Service: is a type of task. Multiple tasks may run the same service.
  - TaskSet: is a group of tasks all related that provides a objective.

"""

from tornado import web
from tornado.log import app_log, gen_log
import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import requests
import os
import docker
from mx import DateTime


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


class AWSAPI(object):
    """
    A wrapper for accessing AWS.
    """
    __TableName__ = 'Services'
    aws_identity_doc_url = 'http://169.254.169.254/latest/dynamic/instance-identity/'

    def __init__(self, apiKeyId=None, secret=None, endpoint=None, region=None):
        self.__apiKey = apiKeyId or os.environ.get('AWS_ACCESS_KEY_ID')
        self.__secret = secret or os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.__endpoint = endpoint or os.environ.get('AWS_DYNAMODB_ENDPOINT')
        self.__region = region or os.environ.get('AWS_REGION')
        self.__session = None
        self.__dbc = None
        self.__dbr = None
        self.__identity_doc = self.__docker_info = {}
        self.__table = None
        self.setup()

    @property
    def session(self):
        if not self.__session:
            app_log.info("Starting new Boto3.Session")
            self.__session = boto3.session.Session(
                aws_access_key_id=self.__apiKey,
                aws_secret_access_key=self.__secret,
                region_name=self.region,
            )
        return self.__session

    @property
    def dbc(self):
        """
        The DynamoDB Low-Level client.
        """
        if not self.__dbc:
            if self.__endpoint:
                app_log.info("Using DynamoDb endpoint: %s" % self.__endpoint)
            self.__dbc = self.session.client('dynamodb', endpoint_url=self.__endpoint)
        return self.__dbc

    @property
    def dbr(self):
        """
        The DynamoDB Resource.
        """
        if not self.__dbr:
            if self.__endpoint:
                app_log.info("Using DynamoDb endpoint: %s" % self.__endpoint)
            self.__dbr = self.session.resource('dynamodb', endpoint_url=self.__endpoint)
        return self.__dbr

    @property
    def table(self):
        """
        The table used by the Overseer
        """
        if self.__table is None:
            response = self.dbc.list_tables()
            app_log.info("list_tables response: %s" % response)
            if self.__TableName__ in response['TableNames']:
                app_log.info("Found existing table: %s" % self.__TableName__)	 
                self.__table = self.dbr.Table(self.__TableName__)
            else:
                self.__table = self.create()
        return self.__table

    @property
    def region(self):
        """
        """
        if self.__region:
            return self.__region
        elif self.__identity_doc:
            return self.__identity_doc.get('region')
        else:
            return ''

    @property
    def instanceId(self):
        """
        The instance id of the EC2 Instance running this service.
        """
        if self.__identity_doc:
            return self.__identity_doc.get('instanceId')
        else:
            return self.__docker_info['ID']

    def setup(self):
        """
        Setup the dynamoDb table if it doesn't exist.
        """
        if os.environ.get('AWS_EXECUTION_ENV'):
            app_log.info("Getting AWS identity document.")
            response = requests.get(self.aws_identity_doc_url + 'document')
            if response.status_code == 200:
                self.__identity_doc = response.json()
        client = docker.DockerClient()
        self.__docker_info = client.info()
        app_log.info("Found instanceId: %s" % self.instanceId)

    def create(self):
        """
        Create the tables for overseer.

            - ContainerId: is the id of the docker container running the service
            - EC2InstanceId: is the id of the EC2 instance running the container
            - TaskId: is the id of the task from the cluster
            - ServiceName: is the name of the service (eg. db1)
            - CurrentStatus: is the current status of the service
        """
        app_log.info("Creating table: %s" % self.__TableName__)
        GlobalSecondaryIndexes = [{
        # Index for services running on an EC2 Instance
            'IndexName': 'TasksByInstanceStatus',
            'KeySchema': [
                {'AttributeName': 'InstanceId', 'KeyType': 'HASH',},  # PartitionKey
                {'AttributeName': 'CurrentStatus', 'KeyType': 'RANGE',}, # SortKey
            ],
            'Projection': { 'ProjectionType': 'ALL', },
        },{
        # Index to search for running services by name
            'IndexName': 'TasksByServiceName',
            'KeySchema': [
                {'AttributeName': 'ServiceName', 'KeyType': 'HASH',},  # SortKey
                {'AttributeName': 'CurrentStatus', 'KeyType': 'RANGE',}, # PartitionKey
            ],
            'Projection': { 'ProjectionType': 'ALL', },
        },]
        # If there is an endpoint then we are using the dynamodb-local service
        # that has a bug where ProvisionedThroughput is required on everything
        # but ignored.
        args = {}
        if self.__endpoint:
            ProvisionedThroughput = {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1,}
            for index in GlobalSecondaryIndexes:
                index['ProvisionedThroughput'] = ProvisionedThroughput
            args['ProvisionedThroughput'] = ProvisionedThroughput
        table = self.dbr.create_table(
            TableName=self.__TableName__,
            KeySchema=[
                {'AttributeName': 'TaskId', 'KeyType': 'HASH',},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'TaskId', 'AttributeType': 'S',},
                {'AttributeName': 'InstanceId', 'AttributeType': 'S',},
                {'AttributeName': 'ServiceName', 'AttributeType': 'S',},
                {'AttributeName': 'CurrentStatus', 'AttributeType': 'S',},
            ],
            GlobalSecondaryIndexes=GlobalSecondaryIndexes,
            BillingMode='PAY_PER_REQUEST',
            **args
        )
        table.wait_until_exists()
        return table

    def newService(self, data):
        """
        Create a new service mapping and return the new service key.
        """
        response = self.table.put_item(Item=data, ReturnValues='ALL_OLD')
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise ValueError("Failed to run newService.")
        # TODO: store the capacity units consumed
        if 'Attributes' in response:
            app_log.warn("newService updated an existing service.")
        app_log.info("newService.response: %s" % response)

    def listServices(self, instanceId=None, status=None):
        """
        List the current services offered by this instance.
        """
        keycond = filterexp = ''
        if instanceId:
            keycond = Key('InstanceId').eq(instanceId)
            if status and status != 'all':
                keycond &= Key('CurrentStatus').eq(status)
            response = self.table.query(
                IndexName='TasksByInstanceStatus', KeyConditionExpression=keycond,
            )
        elif status == 'all':
            response = self.table.scan()
        else:
            if status:
                filterexp = Attr('CurrentStatus').eq(status)
            else:
                filterexp = Attr('CurrentStatus').ne('terminated')
            response = self.table.scan(
                IndexName='TasksByInstanceStatus', FilterExpression=filterexp,
            )
        app_log.info("listServices.response: %s" % response)
        # TODO: store the capacity units consumed.
        return response.get('Items', [])

    def getTask(self, taskId):
        """
        Collect a specific service.
        """
        result = self.table.get_item(Key={'TaskId': taskId,})
        # Probably need to convert some values
        # Could probably store the CapacityUnits.
        return result.get('Item')

    def getTaskByHostname(self, hostname, instanceId=None, status='running'):
        """
        """
        keycond = filterexp = ''
        if instanceId:
            keycond = Key('InstanceId').eq(instanceId)
            if status and status != 'all':
                keycond &= Key('CurrentStatus').eq(status)
            filterexp = Attr('Hostname').eq(hostname)
            response = self.table.query(
                IndexName='TasksByInstanceStatus', 
                KeyConditionExpression=keycond,
                FilterExpression=filterexp,
            )
        else:
            filterexp = Attr('Hostname').eq(hostname)
            if status:
                filterexp &= Attr('CurrentStatus').eq(status)
            else:
                filterexp &= Attr('CurrentStatus').ne('terminated')
            response = self.table.scan(
                IndexName='TasksByInstanceStatus', FilterExpression=filterexp,
            )
        app_log.info("getTaskByHostname.response: %s" % response)
        # TODO: store the capacity units consumed.
        return response.get('Items', [])

    def getService(self, serviceName, instanceId=None, status='running'):
        """
        Get a list of tasks running the requested service. Optionally limit to
        the specified Instance/Node.
        """
        keycond = Key('CurrentStatus').eq(status) & Key('ServiceName').eq(serviceName)
        if instanceId:
            filterexp = Attr('InstanceId').eq(instanceId)
        response = self.table.query(
            IndexName='TasksByServiceName',
            KeyConditionExpression=keycond,
            FilterExpression=filterexp,
        )
        app_log.info('getService.response: %s' % response)
        return response.get('Items', [])

    def deleteService(self, taskId):
        """
        Remove a service.
        """
        response = self.table.delete_item(Key={'TaskId': taskId})
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise ValueError('Service not registered.')

    def clean(self):
        """
        Remove all services.
        """
        scan = self.table.scan(
            ProjectionExpression='#k', 
            ExpressionAttributeNames={'#k': 'TaskId',},
        )
        with self.table.batch_writer() as batch:
            for each in scan['Items']:
                batch.delete_item(Key=each)

    def updateService(self, taskId, **kwargs):
        """
        Update the service.
        """
        exp, vals, para, attrs = [], {}, 'a', {}
        for name, value in kwargs.iteritems():
            if isinstance(value, basestring):
                exp.append('#%s = :%s' % (para, para))
            elif type(value) is list:
                exp.append('#%s = list_append(#%s, :%s)' % (para, para, para))
            elif type(value) in (int, long):
                comp = value > 0 and '+' or '-'
                exp.append('#%s = #%s %s :%s' % (para, para, comp, para))
            else:
                continue
            vals[':%s' % para] = value
            attrs['#%s' % para] = name
            para = chr(ord(para)+1)
        response = self.table.update_item(
            Key={'TaskId': taskId},
            ConditionExpression=Attr('TaskId').eq(taskId),
            UpdateExpression='SET ' + ', '.join(exp),
            ExpressionAttributeValues=vals,
            ExpressionAttributeNames=attrs,
            ReturnValues='UPDATED_NEW',
        )
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise ValueError('Service not registered.')


class AWSBase(web.RequestHandler):
    """
    Base request handler providing the AWS API.
    """
    def initialize(self, awsapi):
        self.api = awsapi


class RegisterHandler(AWSBase):
    """
    Register a new service based on the container and providing optional
    hostname, port mappings.
    """
    __fields__ = (
        'ContainerId', 'ContainerName', 'Hostname', 'IP', 'Port', 'ServiceName',
        'TaskId',
    )

    def get(self):
        """
        Post a new service registration
        """
        response = { 'metadata': {}, }
        missing, data = [], {}
        for field in self.__fields__:
            try:
                data[field] = self.get_argument(field)
            except web.MissingArgumentError, exc:
                missing.append(field)
        if missing:
            response['metadata'].update(
                {'status': 400, 'message': 'Missing arguments: %s' % ', '.join(missing),}
            )
        else:
            now = DateTime.now().Format('%Y-%m-%d %H:%M:%S')
            data['Status'] = [{'Status': 'starting', 'Date': now, 'Message': 'Registration.'},]
            data['CreatedOn'] = now
            data['LastStatusChangedOn'] = now
            data['CurrentStatus'] = 'starting'
            data['InstanceId'] = self.api.instanceId
            self.api.newService(data)
            response['metadata']['status'] = 200
        self.write(JSONEncoder().encode(response))


class StatusHandler(AWSBase):
    """
    Allow services to update their status.
    """
    __fields__ = ('Status', 'Message',)

    def get(self):
        response = { 'metadata': {}, }
        taskId = self.get_argument('TaskId')
        data = {}
        for field in self.__fields__:
            data[field] = self.get_argument(field)
        data['Date'] = DateTime.now().Format('%Y-%m-%d %H:%M:%S')
        CurrentStatus = data['Status']
        LastStatusChangedOn = data['Date']
        try:
            self.api.updateService(
                taskId, 
                CurrentStatus=CurrentStatus, 
                LastStatusChangedOn=LastStatusChangedOn,
                Status=[data,]
            )
        except ValueError, exc:
            response['metadata'].update({'status': 500, 'message': exc.args[0],})
        else:
            response['metadata']['status'] = 200
        self.write(JSONEncoder().encode(response))


class ServicesListHandler(AWSBase):
    """
    Get a list of registered services.
    """
    def get(self):
        """
        Return a list of existing services.
        """
        status = self.get_argument('status', None)
        instanceId = self.get_argument('InstanceId', None)
        if instanceId == 'this':
            instanceId = self.api.instanceId
        services = self.api.listServices(instanceId=instanceId, status=status)
        response = {
            'metadata': {'status': 200,},
            'services': services,
        }
        self.write(JSONEncoder().encode(response))


class ServicesHandler(AWSBase):
    """
    Get a list of registered services.
    """
    def get(self):
        """
        Return a list of existing services.
        """
        return self.render('services.html', title='Current Services')


class GetServiceHandler(AWSBase):
    """
    Request a Database instance to use.
        - ServiceName: the name of the service wanted.
        - InstanceId: limit to tasks running the service on these Instances.
    """
    def get(self):
        serviceName = self.get_argument('ServiceName')
        instanceId = self.get_argument('InstanceId', self.api.instanceId)
        services = self.api.getService(serviceName, instanceId)
        response = {
            'metadata': {'status': 200,},
            'services': services,
            'count': len(services),
        }
        self.write(JSONEncoder().encode(response))


class GetTaskByHostHandler(AWSBase):
    """
    Request a specific task based on its hostname.
    """
    def get(self):
        hostname = self.get_argument('Hostname')
        instanceId = self.get_argument('InstanceId', self.api.instanceId)
        tasks = self.api.getTaskByHostname(serviceName, instanceId)
        response = {
            'metadata': {'status': 200,},
            'tasks': tasks,
            'count': len(tasks),
        }
        self.write(JSONEncoder().encode(response))


class ShutdownHandler(AWSBase):
    """
    Shutdown all running containers on this Node/Instance.
    """
    def get(self):
        instanceId = self.get_argument('InstanceId', None) or self.api.instanceId
        ec2 = self.session.client('ec2')
        response = ec2.describe_tags(Filters=[
            {'Name': 'resource-type', 'Values': ['instance',]},
            {'Name': 'resource-id', 'Values': [instanceId,]},
            {'Name': 'key', 'Values': ['Cluster-Name',]},
        ])
        clusterName = response['Tags'][0]['Value']
        ecs = self.session.client('esc')
        response = ecs.list_tasks(
            cluster=clusterName, containerInstance=instanceId,
        )
        

def getHandlers():
    """
    Return the handlers provided by this module.
    """
    awsapi = AWSAPI()
    return [
        (r'/services', ServicesHandler, dict(awsapi=awsapi)),
        (r'/services/register', RegisterHandler, dict(awsapi=awsapi)),
        (r'/services/status', StatusHandler, dict(awsapi=awsapi)),
        (r'/services/list', ServicesListHandler, dict(awsapi=awsapi)),
        (r'/services/get', GetServiceHandler, dict(awsapi=awsapi)),
        (r'/services/tasks', GetTaskByHostHandler, dict(awsapi=awsapi)),
        (r'/services/shutdown', ShutdownHandler),
    ]

