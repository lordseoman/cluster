#!/bin/bash

if [ "x$AWS_LOGS_ENABLE" != "x" ]; then
    python /root/bin/awslogs-agent-setup.py --non-interactive --configfile=/root/etc/awslogs.conf
    patch -p0 --forward --input /root/patches/x_awslogs.diff
fi

apt-get remove --yes build-essential gcc make
apt-get autoremove --yes
