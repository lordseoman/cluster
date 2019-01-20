"""
API Integration with S3.
"""

import common


class S3(object):
    """
    """
    def __init__(self, api):
        self.api = api

    def list_dir(self, bucket, prefix=None):
        retList, token, kw = set(), None, {}
        total = 0
        while True:
            if token:
                kw['ContinuationToken'] = token
            resp = self.api.s3c.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/', MaxKeys=500, **kw)
            if prefix:
                iterOb = resp['CommonPrefixes']
            else:
                iterOb = resp['Contents']
            if len(iterOb) != resp['KeyCount']:
                print "Only got %d keys not %s" % (len(iterOb), resp['KeyCount'])
            for dirpart in iterOb:
                fname = dirpart['Prefix'].strip('/').split('/')[-1]
                if fname in retList:
                    print "Already exists; %s" % fname
                retList.add(fname)
            total += resp['KeyCount']
            if not resp['IsTruncated']:
                break
            token = resp['NextContinuationToken']
        print "Retreived %d results with %d unique keys." % (total, len(retList))
        return retList

