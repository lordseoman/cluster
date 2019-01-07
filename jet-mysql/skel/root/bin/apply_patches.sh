#!/bin/bash

cd /

if [ -e /root/patches ]; then
    for file in `ls -c1 /root/patches/a_*.diff`; do
        patch -p0 --forward --input $file
    done
fi
