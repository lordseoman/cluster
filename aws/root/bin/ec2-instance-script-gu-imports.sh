#!/bin/bash
#
# This is a specialty cloud-init for EC2 instances setup to run a number of imports
# then close down and exit. These instances run containers that house the DB and usage
# then export prior to shutting down.
#

echo "Setting up /Database and /Usage locations..."
cd /
mkdir /mnt/disc/Database
ln -sv /mnt/disc/Database Database
mkdir /mnt/disc/Usage
ln -sv /mnt/disc/Usage Usage
mkdir /mnt/disc/Usage/exports
for x in {1..3}; do
    mkdir -p /Usage/griffith-${x}/incoming
    mkdir /Usage/griffith-${x}/processing
    mkdir /Usage/griffith-${x}/done
done
chown 1000:1000 -R /Usage/*

echo "Installing database..."
instId=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document  | jq -r .instanceId)
p1="Name=resource-type,Values=instance"
p2="Name=resource-id,Values=${instId}"
dbtarball=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=DBtarball" | jq -r '.Tags[].Value')
mkdir /mnt/disc/data
aws s3 cp s3://obsidian-cluster-share/griffith/${dbtarball} /mnt/disc/data/ --no-progress
cd /Database/
tar -zxf /mnt/disc/data/${dbtarball}
mv mysql-griffith mysql-griffith-1
cp -Rpd mysql-griffith-1 mysql-griffith-2
cp -Rpd mysql-griffith-1 mysql-griffith-3
rm /mnt/disc/data/${dbtarball}

echo "Installing usage to process.."
cd /mnt/disc/data
procDate=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=ProcessDate" | jq -r '.Tags[].Value')
date=$( date -d "${procDate}" )
for x in {-1..1}; do
    ymd=$( date +%Y%m%d -d "$date + $x days" )
    aws s3 cp s3://obsidian-cluster-share/griffith/ARCH_F5_Flow_${ymd}.tgz ./ --no-progress
    tar -zxf ARCH_F5_Flow_${ymd}.tgz
    rm ARCH_F5_Flow_${ymd}.tgz
done
x=0
for y in {0..16..8}; do
    x=$(( $x+1 ))
    cd /Usage/griffith-${x}
    for a in {-1..8}; do
        b=$(( $a+$y ))
        ymd=$( date +"%Y%m%d-%H" -d "$date + $b hours" )
        cp /mnt/disc/data/app/jet/Jet/var/usage/done/F5-Flow-${ymd}* incoming/
    done
done
rm -rf /mnt/disc/data/app
chown 1000:1000 -R /Usage

