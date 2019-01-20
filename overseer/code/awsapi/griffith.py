"""
This script is for running the Griffith Backdated Usage imports.
"""

import aws
import cluster
from s3 import S3
import time

from mx import DateTime
from botocore import exceptions


def createVolume(api, date, avZone, logger=None):
    """
    Create a new Volume.
    """
    dateStr = date.Format('%Y%m%d')
    # Create the volume.
    volName = 'Vol-GriffithProcessor-%s' % dateStr
    tags = {'Mount-Point': '/mnt/disc',}
    volume = api.volumes.create(volName, avZone, 150, 'io1', tags=tags)
    volume.wait_until_available()
    return volume

def runInstance(api, date, avZone, volume, logger=None):
    """
    Start up an instance to run the specified dates.
    """
    dateStr = date.Format('%Y%m%d')
    tags = api.cluster.templates.ec2.GriffithProcessor.tags.dict(
        volname=volume.name,
        procDate=dateStr,
    )
    instName = 'Griffith Processor - %s' % dateStr
    subnet = api.subnets.get(avZone=avZone, private=True)
    inst = api.instances.create(instName, 'c5.4xlarge', subnet, 'GriffithProcessor', tags=tags)
    volume.refresh()
    volume.persistent = False
    return inst

def waitOnTasks(api, tasks, delay=15, attempts=100):
    print "Waiting for tasks to start."
    waiter = api.ecs.get_waiter('tasks_running')
    tries = 1
    while tries <= 3:
        try:
            waiter.wait(
                cluster=api.cluster.name,
                tasks=[ t.id for t in tasks ],
                WaiterConfig={'Delay': delay, 'MaxAttempts': attempts,},
            )
        except exceptions.WaiterError, exc:
            if exc.last_response['failures']:
                print "There was a failure starting tasks: %s" % exc.last_response['failures']
                return False
            else:
                print "Tasks did not start, waiting longer..."
                tries += 1
        else:
            return True
    print "Still didn't get things running."
    return False

def runTasks(api, instance, date, logger=None):
    """
    Run the tasks required to process the days data.

    This means running the following containers in order.
        - overseer: this process provides dynamic config
        - jet-mysql x 3: this provides the database
        - jet-processor x 3: this runs the import then export
    """
    dateStr = date.Format('%Y%m%d')
    groupStr = 'gu-%s' % dateStr
    api.cluster.args['processDate'] = dateStr
    tasks, fails = api.runTask('overseer', taskset=groupStr, instance=instance, wait=False)
    result = waitOnTasks(api, tasks, delay=30, attempts=20) 
    if not result:
        return False
    tasks, fails = api.runTask('jetdb', taskset=groupStr, instance=instance, wait=False)
    result = waitOnTasks(api, tasks, delay=30, attempts=20) 
    if not result:
        return False
    tasks, fails = api.runTask('processor', taskset=groupStr, instance=instance, wait=False)
    result = waitOnTasks(api, tasks, delay=30, attempts=20) 
    if not result:
        return False
    return True

def setupInstance(api, date, avZone, logger=None):
    """
    Wrap the instance setup to cleanup volumes when the instance fails.
    """
    try:
        volume = createVolume(api, date, avZone)
    except:
        print "Failed to create volume."
        raise ValueError()
    try:
        instance = runInstance(api, date, avZone, volume)
    except:
        print "Failed to start instance."
        volume.destroy()
        api.volumes.refresh()
        raise ValueError()
    return instance


class Logger(object):
    """
    """
    topicArn = "arn:aws:sns:us-east-1:918070721808:GriffithCluster"
    subject = "Overseer Cluster Control"

    def __init__(self, api):
        self.api = api
        self.output = []

    def __call__(self, msg, *args):
        now = DateTime.now().Format('%Y/%m/%d %H:%M:%S')
        message = "[%s]: %s" % (now, msg % args)
        self.output.append(message)
        print message

    def msg(self):
        return '\n'.join(self.output)

    def send(self):
        if self.output:
            self.api.sns.publish(
                TopicArn=self.topicArn, Subject=self.subject, Message=self.msg()
            )
            self.output = []


def process(api, staDate, endDate=None):
    """
    Process a date on the provided instance and wait for it to finish.
    """
    if endDate is None:
        endDate = staDate
    this = staDate
    fails = 0
    log = Logger(api)
    idx, zones = 0, api.availability_zones()
    zones.remove('us-east-1d')
    while this <= endDate:
        log("Processing date %s in zone %s", this.Format("%Y-%m-%d"), zones[idx])
        while api.instances.size >= api.cluster.limits.instances:
            log("Waiting for instances to finish.")
            time.sleep(30*60)
            api.instances.refresh()
        log("Launching instance in %s", zones[idx])
        try:
            instance = setupInstance(api, this, zones[idx], logger=log)
        except:
            log("Failed to start instance, removing zone: %s", zones[idx])
            del zones[idx]
            fails += 1
            if fails >= 3:
                log("..breaking due to repeated fails.")
                break
            else:
                continue
        log("Starting tasks on instance (%s) IP: %s in %s", instance.id, instance.ec2.private_ip_address, zones[idx])
        if runTasks(api, instance, this, logger=log):
            log("All tasks started without error..")
            this += DateTime.oneDay
        else:
            log("There wa was a failure starting tasks, destroying.")
            instance.ec2.destroy()
        log.send()
        fails = 0
        idx += 1
        if idx >= len(zones):
            idx = 0
    log.send()

def getFrank():
    with open('/opt/patches/temp/3298hdhb3.txt') as fh:
        v = [ l.strip() for l in fh ]
    return dict(zip(['frank', 'ernie'], v))

def test(api):
    avZone = 'us-east-1e'    
    date = DateTime.DateTimeFrom('2018-05-01')
    dateStr = date.Format('%Y%m%d')
    volume = createVolume(api, date, avZone)
    instance = runInstance(api, date, avZone, volume)
    api.runTask('overseer',taskset='gu-%s' % dateStr,instance=instance,wait=True)
    api.runTask('jetdb',taskset='gu-%s' % dateStr,instance=instance,wait=True)

def getExportUserList(api):
    """
    Look in S3 for users with exported data.
    """
    s3 = S3(api)
    userList = s3.list_dir('obsidian-cluster-share', 'griffith/exports/')
    userList.update(s3.list_dir('obsidian-cluster-share', 'griffith/exports_v2/'))
    userList.discard('00-Global')
    print "Got %d users with export data." % len(userList)
    with open('all_usernames_in_export.txt', 'w') as fh:
        userListV2 = list(userList)
        userListV2.sort()
        for un in userListV2:
            fh.write('%s\n' % un)
    print "..done"


if __name__ == "__main__":
    import sys
    clusterCfg = cluster.Cluster('griffith.yaml', {'realm': 'griffith',})
    api = aws.AWS(cluster=clusterCfg)
    api.cluster.args.update(getFrank())
    args = sys.argv[1:]
    startDate = endDate = None
    if args:
        startDate = DateTime.DateTimeFrom(args.pop(0))
    if args:
        endDate = DateTime.DateTimeFrom(args.pop(0))
    if startDate:
        process(api, startDate, endDate)

