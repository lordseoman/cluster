#!/bin/bash

IMG=$1
VER=$2

docker tag ${IMG}:${VER} 918070721808.dkr.ecr.ap-southeast-2.amazonaws.com/${IMG}:latest
docker tag ${IMG}:${VER} 918070721808.dkr.ecr.ap-southeast-2.amazonaws.com/${IMG}:${VER}

docker push 918070721808.dkr.ecr.ap-southeast-2.amazonaws.com/${IMG}:${VER}
docker push 918070721808.dkr.ecr.ap-southeast-2.amazonaws.com/${IMG}:latest

