#!/bin/bash
#
# We need to export mysql environment variables for /root/bin/run_mysql.sh because
# supervisord does not pass them through.
echo "Exporting MySQL Environment variables.."

if [ -e /root/.env ]; then
    rm /root/.env
fi

if [ "x$DATABASE" != "x" ]; then
    echo "export DATABASE=${DATABASE}" >> /root/.env
fi

echo "export MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}" >> /root/.env
echo "export MYSQL_JET_USERNAME=${MYSQL_JET_USERNAME}" >> /root/.env
echo "export MYSQL_JET_PASSWORD=${MYSQL_JET_PASSWORD}" >> /root/.env

if [ "x$AWS_LOGS_ENABLE" != "x" ]; then
    echo "export AWS_ACCESS_KEY=$AWS_ACCESS_KEY" >> /root/.env
    echo "export AWS_ACCESS_SECRET_KEY=$AWS_ACCESS_SECRET_KEY" >> /root/.env
fi

