#!/usr/bin/env python

import sys, json

def getTagValue(res, name):
    for tag in res.get('Tags', []):
        if tag['Key'] == name:
            return tag['Value']

data = json.load(sys.stdin)
for volume in data['Volumes']:
    if volume['Attachments']:
        continue
    print getTagValue(volume, 'Mount-Point'), volume['VolumeId']

