#!/bin/bash

procDate='20180501'
date=$( date -d "${procDate}" )
echo $date
echo "-=-=-=-=-=-=-"

for x in {-1..1}; do
    ymd=$( date +%Y%m%d -d "$date + $x days" )
    echo "ARCH_F5_Flow_${ymd}.tgz"
done

x=0
for y in {0..16..8}; do
    x=$(( $x+1 ))
    echo "/Usage/griffith-${x}"
    for a in {-1..9}; do
        b=$(( $a+$y ))
        ymd=$( date +"%Y%m%d-%H" -d "$date + $b hours" )
        echo "  - F5-Flow-${ymd}*"
    done
done

