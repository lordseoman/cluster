#!/bin/bash

size=$1

mkdir /mnt/ramdisk
mount -t tmpfs -o size=${size}M,mode=0755 tmpfs /mnt/ramdisk
mkdir /mnt/ramdisk/db
chown -R ec2-user:ec2-user /mnt/ramdisk
cp /etc/fstab /etc/fstab.pre-ramdisk
echo "tmpfs       /mnt/ramdisk  tmpfs  nodev,size=${size}M,mode=0755  0   0" >> /etc/fstab

