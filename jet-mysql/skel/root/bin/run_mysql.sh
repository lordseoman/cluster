#!/bin/bash

source /root/.env

# Catch the exit signal and stop mysql nicely
trap "{ echo Stopping MySQLdb Server..; mysqladmin -p${MYSQL_ROOT_PASSWORD} shutdown; exit 0; }" EXIT

echo "Starting MySQLdb Server.."
/usr/bin/pidproxy /var/run/mysqld/mysqld.pid /usr/bin/mysqld_safe --pid-file=/var/run/mysqld/mysqld.pid

