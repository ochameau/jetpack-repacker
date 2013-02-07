=== REPACK INSTRUCTIONS ===

0/ Setup environnement and download these scripts
```
# We assume that we segregate all these repack files in '/addons' folder
# (Note that this folder can be anywhere else, it is just for sake of clarity)

$ mkdir /addons
$ cd /addons
$ git clone https://github.com/ochameau/jetpack-repacker .
  - or -
$ wget --no-check-certificate https://github.com/ochameau/jetpack-repacker/tarball/master -O - | tar xz
```

1/ Download xpi files

a) From AMO private FTP (suggested way, if you have access to it)
```
$ cd /addons
$ cp amo_db_config.yml.example amo_db_config.yml
$ vi amo_db_config.yml # set database credentials
$ python2.7 scripts/fetch_amo.py
# this will fetch records from the AMO database for every current sdk-based 
# add-on and download the xpi files to ./xpis/.
# to capture errors, grep for 'ERR' eg
# python2.7 scripts/fetch_amo.py 2> errors.txt
# (On 2013/02, it downloaded ~400MB of files.)
```

b) From public FTP 
```
$ cd /addons
$ ./scripts/fetch-ftp.sh
# This script will download all xpi files. You can re-run it at anytime to download only new files.
# but note that remove files from mozilla ftp will be kept locally.
# xpi will be in /addons/ftp/ftp.mozilla.org/pub/mozilla.org/addons/
# (On 2012/07, it downloaded 17GB of files.)
```

2/ Unzip jetpack xpi files
```
# depending from where you downloaded xpi, run one of these scripts:
$ cd /addons
$ ./scripts/unzip-ftp.sh xpis/ src/
$ ./scripts/unzip-amo.sh xpis/ src/
# This script will unzip all jetpack xpi files to /addons/src/jetpack folder
# (On 2012/07, it unpacked 770MB of data)
```

3/ Checkout all SDK released versions
```
$ cd /addons
$ mkdir sdks
$ ./scripts/clone_add_sdk_versions.sh
# It will take some time as it will checkout all tagged versions on git repo
```

4/ Compute repackability
```
$ cd /addons
$ python unpack.py --sdks sdks/ --batch repackability src/jetpack/ > repackability 2>&1
# This will process each addon source code and try to repack it against same SDK version
# and will tell for each addon, which one is safely repackable
```

5/ Compute addons list to repack
```
# remove diffs
$ cat repackability | grep -E "[0-9]+: " > t
# select only repackable and filter only path
$ cat info | grep repackable | grep -oE "^[^:]+" > to-repack
# /addons/to-repack now contains only path to repackable addons
```

4/ Repack selected addons
```
$ mkdir /addons/repacked
$ for i in `cat /addons/to-repack`; do python /addons/repacker/unpack.py repack $i --sdk /addons/sdks/1.8.2 --target /addons/repacked/ ;done
# Replace 1.8.2 with SDK version you want to repack to.
# repacked addons will be available in /addons/repacked/ folder
```

5/ Eventually compute dependencies and detailed info about each addon
```
for i in `cat /addons/to-repack`; do python /addons/repacker/unpack.py deps $i; done > /addons/repacked-info
```

