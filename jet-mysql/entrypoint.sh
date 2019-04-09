#!/bin/bash

if [ -e /var/run/mysqld/mysqld.pid ]; then
   echo "Unsafe shutdown..."
fi

# Output the agent setup logs to the container logs
if [ -e /var/log/awslogs-agent-setup.log ]; then
    cat /var/log/awslogs-agent-setup.log
fi

/root/bin/registerService.py

if [ -e /opt/patches/runContainer.sh ]; then
    echo "Running dynamic update."
    chmod 755 /opt/patches/runContainer.sh
    /opt/patches/runContainer.sh
fi

/root/bin/on-boot.sh

# Run the pre as this sets up the /opt/mysql => /opt/Database/XYZ
/root/bin/setup-mysql-dbdir.sh

# If a database exists then at lease the mysql schema db will exist.
if [ ! -e /opt/mysql/data/mysql ]; then
    /root/bin/serviceStatus.py initialising "Performing initial Db setup."
    /root/bin/initial-setup.sh
    RET=$?
    /root/bin/serviceStatus.py starting "Post initialisation start up."
else
    RET=0
fi

if [ $RET -eq 0 ]; then
    echo "Container started with: $@"
    # This sets up the environment variables to get around supervisor limitations
    /root/bin/pre-supervisor.sh
    service supervisor start
    supervisorctl start $1
    term_handler() {
        /root/bin/serviceStatus.py closing "Stopping MySQL due to term signal."
        supervisorctl stop all
        service supervisor stop
        /root/bin/serviceStatus.py terminated "Shutdown finished."
        exit 0;
    }
    trap 'term_handler' SIGTERM
    /root/bin/serviceStatus.py running "Service started."
else
    echo "MySQL setup failed, starting bash instead of supervisor.."
    /root/bin/serviceStatus.py debugmode "Entering debug mode due to setup failure."
    cat /root/mysql.setup.log
    if [ -e /opt/Database/mysql/logs/mysql.err ]; then
        cat /opt/Database/mysql/logs/mysql.err
    fi
fi

(while true; do sleep 1000; done) & wait
/root/bin/serviceStatus.py terminated "Shutdown finished."
exit 0

