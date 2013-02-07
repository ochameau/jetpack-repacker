#!/bin/bash

P=`pwd`
echo $P
mkdir -p sdks/
for i in `git ls-remote -t http://github.com/mozilla/addon-sdk "refs/tags/[1-9].*" | sed 's:.*/::'`; do 
  if [ ! -d $i ]; then
    echo "clone " $i " ..."
    git clone http://github.com/mozilla/addon-sdk -q --depth 1 $P/sdks/$i
    cd $P/sdks/$i
    git checkout -q $i
  fi
done
