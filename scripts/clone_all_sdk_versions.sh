#!/bin/bash

for i in `git ls-remote -t http://github.com/mozilla/addon-sdk "refs/tags/[1-9].*" | sed 's:.*/::'`; do 
  if [ ! -d $i ]; then
    echo "clone " $i " ..."
    git clone http://github.com/mozilla/addon-sdk -q --branch $i --depth 1 $i; 
  fi
done
