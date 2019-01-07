#!/bin/bash
#
# This script is used when an additional mount point is added for an ec2 instance.
# We do this for databases, the store-processor, the file-reader and other processors.
# The presence of the additional mount are done using the Instance-Mount tag when a 
# new instance container is launched.
#
# The Instance-Mount is passed into this script with the form:
#
#   <device>:<name>,<device>:<name>

instId=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document  | jq -r .instanceId)

IFS=',' read -ra VAR1 <<< "$@"
for MP in "${VAR1[@]}"; do
    IFS=':' read -ra VAR2 <<< "$MP"
    echo "Processing mount for Volume: ${VAR2[1]} on device ${VAR2[0]}"
    # Get the <mount-point volumeid> from the volume
    voldata=$(aws ec2 describe-volumes --filter "Name=tag:Name,Values=${VAR2[1]}" --region us-east-1 | python /root/bin/extractVolume.py)
    IFS=' ' read -ra VAR3 <<< "$voldata"
    echo "Attaching Volume: ${VAR2[1]} Id=${VAR3[1]} at ${VAR3[0]}"
    result=$(aws ec2 attach-volume --device ${VAR2[0]} --volume-id ${VAR3[1]} --instance-id $instId)
    if [ ! -d ${VAR3[0]} ]; then
        echo "Creating mount-point: ${VAR3[0]}"
        mkdir ${VAR3[0]}
    fi
    sleep 1m
    currentfs=$( lsblk -no FSTYPE ${VAR2[0]} )
    if [ "x$currentfs" == "x" ]; then
        echo "Formatting ${VAR2[0]}"
        /sbin/mkfs -t ext4 ${VAR2[0]}
    fi
    echo "Mounting volume: ${VAR2[1]} as device ${VAR2[0]} on ${VAR3[0]}"
    mount -t ext4 ${VAR2[0]} ${VAR3[0]}
    echo "Updating /etc/fstab"
    echo "${VAR2[0]}    ${VAR3[0]}   ext4    defaults,nofail 0   2" >> /etc/fstab
done

