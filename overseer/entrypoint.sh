#!/bin/bash

if [ "x$AWS_EXECUTION_ENV" != "x" ]; then
    region=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
    echo "AWS_DEFAULT_REGION=$region" >> /etc/environment
fi

python /opt/overseer/broadcaster.py &
python /opt/overseer/main.py --reload &

while true; do
    sleep 5
done

