#!/bin/bash

echo "Running on-boot startup script.."

if [ -e /opt/ramdisk ]; then
    if [ ! -e /opt/ramdisk/db ]; then
        mkdir /opt/ramdisk/db
    fi
    chown -R jet:jet /opt/ramdisk/db
fi

if [ "x$TIMEZONE" != "x" ]; then
    CUR_TZ=$( cat /etc/timezone )
    if [ "$TIMEZONE" != "$CUR_TZ" ]; then
        if [ ! -e /usr/share/zoneinfo/$TIMEZONE ]; then
            echo "Invalid timezone ($TIMEZONE) not changing."
        else
            echo "Changing timezone."
            rm /etc/localtime
            ln -sv /usr/share/zoneinfo/$TIMEZONE /etc/localtime
            dpkg-reconfigure -f noninteractive tzdata
        fi
    fi
fi

exit 0
