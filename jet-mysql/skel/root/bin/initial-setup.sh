#!/bin/bash

source /root/defaults

echo "Installing initial database.."
mysql_install_db --user=mysql

if [ -n "$AWS_EXECUTION_ENV" ]; then
    un=$MYSQL_JET_USERNAME
    hn='%.internal'
    pw=$MYSQL_JET_PASSWORD
    GRANT="GRANT ALL ON *.* TO '${un}'@'${hn}' IDENTIFIED BY '${pw}';GRANT SHOW DATABASES ON *.* TO '${un}'@'${hn}';"
else
    GRANT=""
fi

sql=$(cat <<EOF
GRANT ALL ON *.* TO '${MYSQL_JET_USERNAME}'@'localhost' IDENTIFIED BY '${MYSQL_JET_PASSWORD}';
GRANT ALL ON *.* TO '${MYSQL_JET_USERNAME}'@'127.0.0.1' IDENTIFIED BY '${MYSQL_JET_PASSWORD}';
GRANT ALL ON *.* TO '${MYSQL_JET_USERNAME}'@'${IP}/${MASK}' IDENTIFIED BY '${MYSQL_JET_PASSWORD}';
GRANT ALL ON *.* TO '${MYSQL_JET_USERNAME}'@'${MACHINE}' IDENTIFIED BY '${MYSQL_JET_PASSWORD}';
GRANT SHOW DATABASES ON *.* TO '${MYSQL_JET_USERNAME}'@'localhost';
GRANT SHOW DATABASES ON *.* TO '${MYSQL_JET_USERNAME}'@'127.0.0.1';
GRANT SHOW DATABASES ON *.* TO '${MYSQL_JET_USERNAME}'@'${IP}/${MASK}';
GRANT SHOW DATABASES ON *.* TO '${MYSQL_JET_USERNAME}'@'${MACHINE}';
$GRANT
SET PASSWORD FOR 'root'@'localhost' = PASSWORD('${MYSQL_ROOT_PASSWORD}');
SET PASSWORD FOR 'root'@'127.0.0.1' = PASSWORD('${MYSQL_ROOT_PASSWORD}');
SET PASSWORD FOR 'root'@'::1' = PASSWORD('${MYSQL_ROOT_PASSWORD}');
SET PASSWORD FOR 'root'@'${FQDN}' = PASSWORD('${MYSQL_ROOT_PASSWORD}');
FLUSH PRIVILEGES;
EOF
)

nohup /usr/bin/mysqld_safe --pid-file=/var/run/mysqld/mysqld.pid > /root/mysql.setup.log 2>&1 &
pid=$!

echo -n "Waiting for MySQL to start "
maxcounter=60
counter=1
while ! mysql -uroot -e "show databases;" > /dev/null 2>&1; do
    sleep 1
    counter=`expr $counter + 1`
    if [ $counter -gt $maxcounter ]; then
        echo "FAILED"
        exit 1
    fi;
    echo -n "."
done
echo "  OK"

echo "Setting permissions for jetdb.."
mysql -uroot -e "${sql}"
mysqladmin -uroot -p"${MYSQL_ROOT_PASSWORD}" shutdown

echo "Setup complete."
