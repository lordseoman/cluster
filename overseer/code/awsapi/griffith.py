"""
This script is for running the Griffith Backdated Usage imports.
"""

import aws
import cluster

from mx import DateTime


def createVolume(api, date, avZone):
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

def runInstance(api, date, avZone, volume):
    """
    Start up an instance to run the specified dates.
    """
    dateStr = date.Format('%Y%m%d')
    tags = {
        'Mount': '/dev/sdc:%s' % volume.name,
        'Instance-Type': 'GriffithProcessor',
        'ProcessDate': dateStr,
        'DBtarball': 'db-griffith-clustered-imports-clean-20181009.tgz',
    }
    instName = 'Griffith Processor - %s' % dateStr
    subnet = api.subnets.get(avZone=avZone, private=True)
    inst = api.instances.create(instName, 'c5.4xlarge', subnet, 'GriffithProcessor', tags=tags)
    volume.refresh()
    volume.persistent = False
    return inst

def runTasks(api, instance, date):
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
    api.runTask('overseer', taskset=groupStr, instance=instance, wait=True)
    api.runTask('jetdb', taskset=groupStr, instance=instance, wait=True)
    api.runTask('processor', taskset=groupStr, instance=instance, wait=True)

def processDate(api, staDate, endDate=None):
    """
    Process a date on the provided instance and wait for it to finish.
    """
    if endDate is None:
        endDate = staDate
    this = staDate
    fails = 0
    idx, zones = 0, api.availability_zones()
    while this <= endDate:
        try:
            volume = createVolume(api, this, zones[idx])
        except:
            print "Failed to create volume."
            fails += 1
            if fails >= 3:
                print "..breaking due to repeated fails."
                break
            else:
                continue
        try:
            inst = runInstance(api, this, zones[idx], volume)
        except:
            print "Failed to start instance."
            volume.destroy()
            api.volumes.refresh()
            fails += 1
            if fails >= 3:
                print "..breaking due to repeated fails."
                break
            else:
                continue
        fails = 0
        idx += 1
        if idx >= len(zones):
            idx = 0
        runTasks(api, inst, this)
        this += DateTime.oneDay
    print "All tasks started.."

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


if __name__ == "__main__":
    import sys
    clusterCfg = cluster.Cluster('griffith.yaml', {'realm': 'griffith',})
    api = aws.AWS(cluster=clusterCfg)
    api.cluster.args.update(getFrank())

