#!/bin/bash

subnetType=$1

containerArn=$(curl -s http://localhost:51678/v1/metadata | jq -r .ContainerInstanceArn)
aws ecs put-attributes --cluster Jet-Cluster --attributes "name=obsidian.subnet-type,value=${subnetType},targetType=container-instance,targetId=$containerArn"

