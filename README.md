```
$ python unpack.py -h
usage: SDK addons repacker [-h] [--batch] [--target TARGET] [--force] [--diff]
                           [--diffstat] [--sdk SDK] [--sdks SDKS]
                           {deps,checksum,unpack,repackability,repack} path

Available actions:
 - `deps`: display dependencies used by the addon
 - `checksum`: verify that the addon is only using official SDK files
 - `unpack`: create a source package out of an "compiled" addon
 - `repackability`: do various sanity check to see how safe the repack would be (requires `--sdks` argument)
 - `repack`: rebuild an addon with another SDK version (requires `--sdk` argument)

positional arguments:
  {deps,checksum,unpack,repackability,repack}
                        Action to execute
  path                  path to either a xpi file or an extension folder to
                        process

optional arguments:
  -h, --help            show this help message and exit
  --batch               Process `path` argument as a folder containing
                        multiple addons
  --target TARGET       Folder where to put repacked xpi file(s)
  --force               Force unpack/repack even if checksums are wrong and
                        addon are using a patched SDK version.
  --diff                Print a diff patch between original XPI and repacked
                        one.
  --diffstat            Print a diff statistics between original XPI and
                        repacked one.
  --sdk SDK             Path to SDK folder to use for repacking.
  --sdks SDKS           Path to the directory with each released SDK version.
```

```
# Print SDK version use for a given addon and which packages/modules is it using
$ python unpack.py deps addon.xpi
addon.xpi; 1.2.1; {"addon-kit": ["hotkeys", "tabs", "widget"], "auf-trollbook-posten": ["main"]}
```

```
# Verify all SDK files shipped in the xpi and ensure that checksums are original ones
$ python unpack.py checksum addon.xpi
addon.xpi; 1.2.1; OK; []     <-- [] means no patched files. otherwise you get the list of non-official files
```

```
# Unpack an xpi to sources files
$ mkdir addon/
$ python unpack.py unpack addon.xpi --target addon/
$ ls -R addon
addon:
data  lib  locale  package.json

addon/data:

addon/lib:
main.js

addon/locale:
```

```
# Repack a given addon with a given SDK version
$ cd .../repacker
$ python unpack.py repack my-addon.xpi --sdk /path/to/a/sdk/folder
Successfully repacked my-addon.xpi to my-addon-repacked.xpi
```

```
# Sanity check for a given addon. Ensure that the repacker works fine and that the given xpi hasn't be manually modified.
$ cd .../repacker
$ cd sdks/
$ ./clone_all_sdk_versions.sh
$ cd ..
$ python unpack.py repackability my-addon.xpi --sdks /absolute/path/to/sdks/folder
Successfully repacked my-addon.xpi to my-addon-repacked.xpi
```

