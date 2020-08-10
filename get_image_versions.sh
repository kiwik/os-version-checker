#!/bin/bash

dpkg-query -W --showformat '${Status} ${Package} ${Version}\n' $(dpkg -l | tail -n +6 | tr -s ' ' | cut -d ' ' -f2) | grep ^install | cut -d ' ' -f4,5 > ./images_versions/"$1".txt
echo "$1" >> ./images_versions/images_names.txt