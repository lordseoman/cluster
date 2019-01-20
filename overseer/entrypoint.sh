#!/bin/bash

if [ "x$AWS_EXECUTION_ENV" != "x" ]; then
    region=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
    echo "AWS_DEFAULT_REGION=$region" >> /etc/environment
fi

python /opt/overseer/broadcaster.py &
python /opt/overseer/main.py --reload &

term_handler() {
    echo "Interupted by TERM" 
    exit 0;
}
trap 'term_handler' SIGTERM
(while true; do sleep 1000; done) & wait
exit 0
