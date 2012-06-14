```
$ python unpack.py -h
usage: SDK addons repacker [-h] [--batch] [--target TARGET]
                           {deps,checksum,unpack,repack} path

Available actions:
 - `deps`: display dependencies used by the addon
 - `checksum`: verify that the addon is only using official SDK files
 - `unpack`: create a source package out of an "compiled" addon
 - `repack`: rebuild an addon with another SDK version (need SDK `cfx` application)

positional arguments:
  {deps,checksum,unpack,repack}
                        Action to execute
  path                  path to either a xpi file or an extension folder to
                        process

optional arguments:
  -h, --help            show this help message and exit
  --batch               Process `path` argument as a folder containing
                        multiple addons
  --target TARGET       Folder where to put repacked xpi file(s)
```

```
$ python unpack.py deps addon.xpi
345003/; 1.2.1; {"addon-kit": ["hotkeys", "tabs", "widget"], "auf-trollbook-posten": ["main"]}
```

```
$ python unpack.py checksum addon.xpi
345003/; 1.2.1; OK; []     <-- [] means no patched files. otherwise you get the list of non-official files
```

```
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
$ cd .../addon-sdk
$ source bin/activate
$ cd .../unpacker
$ python unpack.py repack 345003/
Successfully repacked 345003/ to 345003-repacked.xpi
```

