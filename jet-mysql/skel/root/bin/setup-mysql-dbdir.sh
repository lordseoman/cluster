#!/bin/bash
#
# Setup the MySQL database location
# This is called before the initial-setup check and allows an existing database
# to be selected from the Environment. Thus multiple databases can is used on the
# one Instance.
#
if [ "x$DATABASE" == "x" ]; then
    dbdir="/opt/Database/mysql"
else
    dbdir="/opt/Database/mysql-${DATABASE}"
fi

# Create a container local symlink to the database directory.
if [ -e /opt/mysql ]; then
    rm /opt/mysql
fi
if [ ! -e $dbdir ]; then
    mkdir -p $dbdir/binlogs
    mkdir -p $dbdir/data
    mkdir -p $dbdir/logs
fi
chown -R mysql:mysql $dbdir
ln -sv $dbdir /opt/mysql

