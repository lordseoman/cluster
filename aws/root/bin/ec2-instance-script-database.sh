#!/bin/bash

if [ ! -d /Database/data ]; then
    mkdir /Database/data
fi

case "$1" in
    'empty')
        mkdir /Database/mysql
        ;;
    'griffith')
        cd /Database
        aws s3 cp s3://obsidian-cluster-share/db-mysql-griffith-20181009.tgz data/
        tar -zxf data/db-mysql-griffith-20181009.tgz
        cd /
        ;;
    'infosat')
        cd /Database
        aws s3 cp s3://obsidian-cluster-share/db-mysql-infosat-latest.tgz data/
        tar -zxf data/db-mysql-latest.tgz
        cd /
        ;;
    *)
        mkdir /Database/mysql
        ;;
esac

