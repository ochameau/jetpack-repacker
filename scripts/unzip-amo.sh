#!/bin/bash

# `ftp` folder should be a clone of ftp://ftp.mozilla.org/pub/mozilla.org/addons/
# `src` will contain unzipped addons content
# `src/jetpack/` will contain all jetpack addons
# `src/xul` will contain other kind of addons

FTP_DIR=$1
SRC_DIR=$2
# AMO script only download jetpack addons
KIND=jetpack

mkdir -p $SRC_DIR/jetpack

for XPI in $(ls -d $FTP_DIR/*.xpi)
do
  ID=$(basename $XPI)
  # echo $XPI $KIND $ID
  DST_DIR=$SRC_DIR/$KIND/$ID
  mkdir -p $DST_DIR
  echo $XPI $DST_DIR
  unzip $XPI $DST_DIR && echo "unziped $ID" || echo "Failed to unzip $ID"
#  unzip -oq $XPI -d $DST_DIR || echo "Failed to unzip $ID"
done
