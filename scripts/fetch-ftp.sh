#!/bin/bash
mkdir -p /addons/ftp
lftp ftp://ftp.mozilla.org/ -e "mirror /pub/mozilla.org/addons /addons/ftp -c -e --parallel=10 -v --log /addons/ftp-log ; quit"
