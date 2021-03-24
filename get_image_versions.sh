#!/bin/bash

if [ ! -d "./images_versions/$2" ]; then
    mkdir -p "./images_versions/$2"
fi

apt-get update
apt-get --just-print upgrade 2>&1 | perl -ne 'if (/Inst\s([\w,\-,\d,\.,~,:,\+]+)\s\[([\w,\-,\d,\.,~,:,\+]+)\]\s\(([\w,\-,\d,\.,~,:,\+]+)\)? /i) {print "$1 $2 $3\n"}' > ./images_versions/"$2"/"$1".txt
dpkg-query -W --showformat '${Status} ${Package} ${Version}\n' $(dpkg -l | tail -n +6 | tr -s ' ' | cut -d ' ' -f2) | grep ^install | cut -d ' ' -f4,5 >> ./images_versions/"$2"/"$1".txt