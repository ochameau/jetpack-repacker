#!/bin/bash

for i in `./get_sdk_released_versions.sh`; do 
  if [ ! -d $i ]; then
    echo "clone " $i " ..."
    git clone http://github.com/mozilla/addon-sdk -q --branch $i --depth 1 $i; 
  fi
done
