"""
This module provide common bases for the AWS Boto3 API.
"""

# default that allows None values
_object = object()


class DictMapper(object):
    """
    Provide an object interface to a dictionary.
    """
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

    def keys(self):
        return self.data.keys()


class Wrapper(object):
    """
    Basic wrapper for access to dictionary data responses.
    """
    def __init__(self, data):
        self.data = data

    @property
    def id(self):
        return self.data['Id']


class AWSObject(object):
    """
    AWS Objects wrap the Dictionary responses.
    """
    __id__ = 'Id'
    __arn__ = 'Arn'
    __tags__ = 'Tags'

    def __init__(self, aws, data):
        self.aws = aws
        self.data = data

    @property
    def arn(self):
        if self.__arn__ and self.__arn__ in self.data:
            return self.data[self.__arn__]

    @property
    def id(self):
        if self.__id__ and self.__id__ in self.data:
            return self.data[self.__id__]
        elif self.arn:
            return self.arn.split('/')[-1]
        else:
            return None

    def setTag(self, name, value):
        """
        Set a tag.
        """
        response = self.aws.ec2c.create_tags(
            Resources=[self.id,], Tags=[{'Key': name, 'Value': value,}]
        )

    def getTagValue(self, name):
        """
        Get the value for the named tag.
        """
        name = name.lower()
        for tag in self.tags:
            # Inconsistency here where ec2c has Tags/Key/Value but ECS has tags/key/value
            if self.__tags__[0].isupper():
                field, value = 'Key', 'Value'
            else:
                field, value = 'key', 'value'
            if tag[field].lower() == name:
                return tag[value]

    @property
    def tags(self):
        """
        Lazy collection of the resources tags.
        """
        if self.__tags__ and self.__tags__ in self.data:
            return self.data[self.__tags__]
        else:
            return []

    @property
    def name(self):
        return self.getTagValue('Name')

def convertTags(items, key='key', attrs=None):
    """
    Convert a dictionary into key, value list
    """
    attrs = attrs or {}
    retList = []
    for field, value in items.iteritems():
        retList.append({key: field, 'value': value % attrs})
    return retList




