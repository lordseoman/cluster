#!/bin/bash

echo "Performing initial EC2 Instance setup."

if [ "x$AWS_DEFAULT_REGION" == "x" ]; then
    export AWS_DEFAULT_REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
fi

# Call scripts based on instance-type
instId=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document  | jq -r .instanceId)
p1="Name=resource-type,Values=instance"
p2="Name=resource-id,Values=${instId}"

mountpoint=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=Mount" | jq -r '.Tags[].Value')
instType=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=Instance-Type" | jq -r '.Tags[].Value')
ramdisk=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=Ramdisk" | jq -r '.Tags[].Value')

if [ -n "$mountpoint" ]; then
    /root/bin/ec2-instance-script-mount.sh $mountpoint
fi

case "$instType" in
    "database")
        db=$(aws ec2 describe-tags --filters "${p1}" "${p2}" "Name=key,Values=Database" | jq -r '.Tags[].Value')
        /root/bin/ec2-instance-script-database.sh $db
        ;;
    "GriffithProcessor")
        /root/bin/ec2-instance-script-gu-imports.sh
        ;;
esac

if [ -n "$ramdisk" ]; then
    /root/bin/ec2-instance-script-ramdisk.sh $ramdisk
fi

if [ ! -d /mnt/patches ]; then
    mkdir /mnt/patches
    chown ec2-user:ec2-user /mnt/patches
fi

