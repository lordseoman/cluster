#!/bin/bash

echo "Running EC2 Instance update.."

if [ -d /mnt/patches ]; then
    aws s3 sync s3://obsidian-s3/patches/ /mnt/patches --no-progress
    chmod 755 /mnt/patches/*.sh
    chmod 755 /mnt/patches/jet/*.sh
    chmod 755 /mnt/patches/root/*.sh
fi

aws s3 sync s3://obsidian-s3/aws/home/ /home/ec2-user/ --no-progress
chmod 755 /home/ec2-user/bin/*

