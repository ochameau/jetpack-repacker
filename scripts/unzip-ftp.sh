#!/bin/bash

# `ftp` folder should be a clone of ftp://ftp.mozilla.org/pub/mozilla.org/addons/
# `src` will contain unzipped addons content
# `src/jetpack/` will contain all jetpack addons
# `src/xul` will contain other kind of addons

FTP_DIR=$1
SRC_DIR=$2

mkdir -p $SRC_DIR/xul
mkdir -p $SRC_DIR/jetpack

#set -x
for XPI_DIR in $(ls -d $FTP_DIR/*/)
do
  # Retrieve most recent xpi file
  XPI=$(ls -t $XPI_DIR*.xpi 2>/dev/null | head -1)
  # We may not have any xpi file ...
  if ! test $XPI; then
    continue
  fi

  # Check if that's a jetpack addon or not
  KIND=xul
  if $(unzip -l $XPI | grep -q harness-options.json); then 
    KIND=jetpack
  else
    # avoid unpacking xul addons
    continue
  fi
  ID=$(basename $XPI_DIR)
  # echo $XPI $KIND $ID
  DST_DIR=$SRC_DIR/$KIND/$ID
  mkdir -p $DST_DIR
  unzip -oq $XPI -d $DST_DIR || echo "Failed to unzip $ID"
done
