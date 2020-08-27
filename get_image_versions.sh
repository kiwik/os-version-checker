#!/bin/bash

if [ ! -d "./images_versions/$2" ]; then
    mkdir -p "./images_versions/$2"
fi
dpkg-query -W --showformat '${Status} ${Package} ${Version}\n' $(dpkg -l | tail -n +6 | tr -s ' ' | cut -d ' ' -f2) | grep ^install | cut -d ' ' -f4,5 > ./images_versions/"$2"/"$1".txt
sleep 20m