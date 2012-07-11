from zipfile import ZipFile
import sys
import simplejson as json
import re
import os, errno
import tempfile
import shutil
import subprocess
import hashlib
import urllib

JETPACK_HASH_URL = "https://raw.github.com/mattbasta/amo-validator/master/validator/testcases/jetpack_data.txt"

# Build a big hashtable that can be queried like this:
# - for a package file:
#  jetpack_hash_table[$sdkVersion]["packages"][$packageName][$sectionName][$filePath]
# - for a bootstrap file (from "python-lib/cuddlefish/app-extension" folder)
#  jetpack_hash_table[$sdkVersion]["bootstrap"][$filePath]
CACHED_HASH_TABLE = None
def getJetpackHashTable():
  global CACHED_HASH_TABLE
  if CACHED_HASH_TABLE:
    return CACHED_HASH_TABLE
  hash_table = {}
  data_file = os.path.join(os.path.dirname(__file__),
                                   "jetpack_data.txt")
  if not os.path.exists(data_file):
    try:
      print "Dowloading jetpack hash data file ..."
      urllib.urlretrieve(JETPACK_HASH_URL, data_file)
      print "Successfully downloaded to " + data_file
    except Exception, e:
      raise Exception("Unable to download jetpack hash data file", e)
  data = open(data_file)

  for line in [x.split() for x in data]:
    path = line[0].split("/")
    version = line[1]
    hash = line[2]

    if not version in hash_table:
      hash_table[version] = {
        "packages": {},
        "bootstrap": {} 
      }
    by_version = hash_table[version]

    # Catch boostrap files from app-extension folder
    # Ignore defaults/preferences/prefs.js (isn't in xpi file)
    if len(path) > 4 and path[3] == "app-extension" and not "prefs.js" in path:
      # Get the relative path from "app-extension", in order to end up
      # with "bootstrap.js" and "components/harness.js"
      file = "/".join(path[path.index("app-extension")+1:])
      by_version['bootstrap'][file] = hash

    # Otherwise, we only care about addon-kit/api-utils packages files
    elif len(path) > 2 and path[1] == "packages":
      package = path[2]
      section = path[3]
      # we only care about lib and data sections.
      if not section in ["lib", "data"]:
        continue
      file = "/".join(path[4:])
      if not package in by_version["packages"]:
        by_version["packages"][package] = {}
      by_package = by_version["packages"][package]
      if not section in by_package:
        by_package[section] = {}
      by_section = by_package[section]
      by_section[file] = hash

  # Save this hash table in cache in order to avoid reading this file
  # for each addon
  CACHED_HASH_TABLE = hash_table

  return hash_table


# Get list of packages shipped on the addon
def getPackages(manifest):
  metadata = manifest['metadata']
  return metadata.keys()

# Retrieve main module key for its entry in manifest
# i.e.  either uri "resource://jid-addon-name-lib/main.js" (SDK < 1.4)
#          or path "addon-name/lib/main.js" (SDK >= 1.4)
def getMainEntryKey(options, manifest):
  # SDK version >= 1.4 has the entry key in `mainPath` attribute
  if "mainPath" in options:
    return options["mainPath"]
  # SDK < 1.4 doesn't, we need to execute a dynamic search over rootPaths resource URLs
  elif 'rootPaths' in options:
    # We normalize `main`. This attribute is a the module name without the .js extension
    main = options['main'] + ".js"
    for path in options['rootPaths']:
      mainURI = path + main
      if mainURI in manifest:
        return mainURI
    raise Exception("Unable to find main module in manifest dict by iteration over rootPaths")
  else:
    raise Exception("Unsupported manifest, without mainPath, nor rootPaths attributes")

def getAddonDependencies(options):
  # SDK < ?? manifest doesn't contain any requirements
  if not "manifest" in options:
    raise Exception("Unsupported SDK version, without manifest")

  manifest = options["manifest"]

  # SDK < ?? manifest is an array with requirements
  if isinstance(manifest, list):
    raise Exception("Unsupported SDK version, with a manifest array instead of dict")

  deps = dict()
  
  # Add a module to the returned dependencies dict
  # Returns True if this module was already registered
  def addModule(package, module):
    if not package in deps:
      deps[package] = list()
    if module in deps[package]:
      return True
    else:
      deps[package].append(module)
      return False

  # Process a manifest entry
  def processEntry(entry):
    packageName = entry["packageName"]

    moduleName = None
    if "moduleName" in entry: # SDK >= 1.0b5
      moduleName = entry["moduleName"]
    elif "name" in entry: # SDK < 1.0b5
      moduleName = entry["name"]
    else:
      raise Exception("Unknown form of module name in requirements entry")

    # Avoid infinite loop by stopping recursion
    # when a module is already in dependencies list
    if addModule(packageName, moduleName):
      return

    # We do not care about SDK packages dependencies
    if packageName in ["addon-kit", "api-utils"]:
      return

    requirements = None
    if "requirements" in entry: # SDK >= 1.0b5
      requirements = entry["requirements"]
    elif "requires" in entry: # SDK < 1.0b5
      requirements = entry["requires"]
    else:
      raise Exception("Unknown requirements form")

    for reqname, val in requirements.items():
      if reqname == "self":
        addModule("addon-kit", "self")
      elif reqname == "chrome":
        addModule("api-utils", "chrome")
      elif reqname == "@packaging":
        addModule("api-utils", "@packaging")
      elif reqname == "@loader":
        addModule("api-utils", "@loader")
      else:
        key = None
        if "path" in val: # SDK >= 1.4
          key = val["path"]
        elif "uri" in val: # SDK >= 1.0b5 and < 1.4
          key = val["uri"]
        elif "url" in val: # SDK < 1.0b5
          key = val["url"]
        else:
          raise Exception("unknown form of requirements entry: " + str(val))
        
        processEntry(manifest[key])

  
  mainKey = getMainEntryKey(options, manifest)
  if mainKey in manifest:
    processEntry(manifest[mainKey])
  else:
    raise Exception("unable to find main module key in manifest")
  
  return deps



def getFileHash(zip, file):
  return hashlib.sha256(zip.read(file)).hexdigest()

# Verify checksums of app template file
# like bootstrap.js and components/harness.js
def verifyBootstrapFiles(zip, version):
  bad_files = []
  jetpack_hash_table = getJetpackHashTable()
  hash_table = jetpack_hash_table[version]["bootstrap"]
  for file, officialHash in hash_table.items():
    if officialHash != getFileHash(zip, file):
      bad_files.append(file)
  return bad_files

# Verify checksums of a given package
def verifyPackageFiles(zip, manifest, version, package):
  bad_files = []
  jetpack_hash_table = getJetpackHashTable()
  hash_table = jetpack_hash_table[version]["packages"][package]

  for file, section, relpath in getPackagesFiles(zip, version, manifest, package):
    # we verify only html and js files
    if not (file.endswith(".js") or file.endswith(".html")):
      continue

    if not relpath in hash_table[section] or \
      hash_table[section][relpath] != getFileHash(zip, file):
      bad_files.append(file)
  return bad_files

# Create a fake of Zip object but against a directory
class FakeZip:
  def __init__(self, path):
    self.path = path

  def read(self, name):
    return open(os.path.join(self.path, name), "r").read() 

  def namelist(self):
    l = list()
    for top, dirs, files in os.walk(self.path):
      for nm in files:       
        l.append( os.path.relpath(os.path.join(top, nm), self.path) )
    return l

  def getinfo(self, name):
    class Info(object):
      def __init__(self, name):
        self.originalName = name
        self.filename = None
    return Info(name)

  def extract(self, info):
    name = info.originalName # path in zip file
    path = info.filename # absolute path on fs
    # ensure that containing folder exists
    parentFolder = os.path.dirname(path)
    if not os.path.exists(parentFolder):
      os.makedirs(os.path.dirname(path))
    shutil.copy(os.path.join(self.path, name), path)


# Compute the prefix used in old SDK version for 
# folders in resources/
def getJidPrefix(manifest):
  jid = manifest['jetpackID']
  uuidRe = r"^\{([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\}$"
  prefix = jid.lower().replace("@", '-at-').replace(".", '-dot-')
  return re.sub(uuidRe, r'\1', prefix) + "-"

# Get an iterator on files living in resources/ folder
# each entry is an tuple of (
#  path in zip file, 
#  section name (data, lib, test),
#  relative path of a file from a section folder
# )
def getPackagesFiles(zip, version, manifest, package):
  packagePath = None
  if version[:2] == "1." and int(version[2]) >= 4:
    # SDK >=1.4 have simplified resources folder layout
    packagePath = package
  else:
    # Older version are still using `jid` as prefix for folders in resources/
    packagePath = getJidPrefix(manifest) + package

  for file in zip.namelist():
    # Yield only given package files
    if not file.startswith("resources/" + packagePath):
      continue
    # Ignore folders
    if file[-1] == "/":
      continue
    # Compute the relative path for this file,
    # from the section folder (i.e. lib or data folder)
    relpath = file.replace("resources/" + packagePath, "")
    relpath = relpath[1:] # remove either '-' (<1.4) or '/' (>=1.4)
    relpath = relpath.split("/")
    section = relpath[0] # retrieve the section, either 'lib' or 'data'
    relpath = "/".join(relpath[1:])

    yield file, section, relpath


def processAddon(path, args):
  if os.path.isdir(path):
    zip = FakeZip(path)
  elif "xpi" in os.path.splitext(path)[1]:
    zip = ZipFile(path)
  else:
    raise Exception("`path` should be either a xpi file or an addon directry")

  manifest = None
  try:
    manifest = json.loads(zip.read("harness-options.json"))
  except Exception, e:
    raise Exception("Missing harness-options.json file, this isn't a jetpack addon.")

  version = None
  if "sdkVersion" in manifest:
    version = manifest["sdkVersion"]
  else:
    version = "pre-manifest-version"

  if args.action == "deps":
    deps = getAddonDependencies(manifest)
    # Sort modules in dependencies dictionnary
    for package, modules in deps.items():
      modules.sort()
    print path + "; " + version + "; " + json.dumps(deps)
  elif args.action == "checksum":
    bad_files = verify_addon(zip, version, manifest)
    res = None
    if len(bad_files) == 0:
      res = "OK"
    else:
      res = "KO"
    print path + "; " + version + "; " + res + "; " + json.dumps(bad_files)
  elif args.action == "unpack":
    bad_files = verify_addon(zip, version, manifest)
    if not args.force and len(bad_files) > 0:
      raise Exception("Unable to unpack because of wrong checksum or unknown files: ", bad_files)
    unpack(zip, version, manifest, args.target)
    print path + " unpacked to " + args.target
  elif args.action == "repack":
    bad_files = verify_addon(zip, version, manifest)
    if not args.force and len(bad_files) > 0:
      raise Exception("Unable to repack because of wrong checksum or unknown files: ", bad_files)
    repacked_path = repack(path, zip, version, manifest, args.target)
    # Eventually do a diff between original xpi and repacked one
    if args.diff:
      print_diff(path, repacked_path)
  else:
    raise Exception("Unsupported action:", args.action)

def verify_addon(zip, version, manifest):
  jetpack_hash_table = getJetpackHashTable()
  if not version in jetpack_hash_table:
    raise Exception("This addon is build with '" + version + "' SDK version, whose doesn't have official hashes.")
  bad_files = verifyBootstrapFiles(zip, version)
  packages = getPackages(manifest)
  if "addon-kit" in packages:
    bad_files.extend(verifyPackageFiles(zip, manifest, version, "addon-kit"))
  if "api-utils" in packages:
    bad_files.extend(verifyPackageFiles(zip, manifest, version, "api-utils"))
  return bad_files

def repack(path, zip, version, manifest, target):
  deps = getAddonDependencies(manifest)
  if "api-utils" in deps.keys():
    raise Exception("We are only able to repack addons which use only high-level APIs from addon-kit package")

  # Unpack the given addon to a temporary folder
  tmp = tempfile.mkdtemp(prefix="tmp-addon-folder")
  unpack(zip, version, manifest, tmp)
  
  # Execute `cfx xpi`
  shell = False
  if sys.platform == 'win32':
    shell = True
  p = subprocess.Popen(["cfx", "xpi"], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
  std = p.communicate()
  basename = os.path.basename(path)
  if len(basename) == 0:
    basename = os.path.basename(os.path.dirname(path))
  xpi_path = os.path.join(target, basename + "-repacked.xpi")
  if "Exporting extension to " in std[0]:
    xpiName = re.search(" ([^ ]+\.xpi)", std[0]).group(1)
    tmpXpiPath = os.path.join(tmp, xpiName)
    shutil.move(tmpXpiPath, xpi_path)
    print "Successfully repacked", path, "to", xpi_path
  else:
    print "Error while building the new xpi: "
    print std[0]
    print std[1]

  # Delete the temporary folder
  shutil.rmtree(tmp)

  return xpi_path

import filecmp
from difflib import unified_diff
def print_diff(zipA, zipB):
  stat = True
  # in batch mode, original zip may be a uncompressed addon directory
  if os.path.isdir(zipA):
    pathA = zipA
  else:
    pathA = tempfile.mkdtemp(prefix="xpi-A")
    ZipFile(zipA).extractall(pathA)

  pathB = tempfile.mkdtemp(prefix="xpi-B")
  ZipFile(zipB).extractall(pathB)

  dircmp = filecmp.dircmp(pathA, pathB)

  left_only = []
  right_only = []
  diff_files = []
  def recurse(path, dircmp):
    left_only.extend([os.path.join(path, x) for x in dircmp.left_only])
    right_only.extend([os.path.join(path, x) for x in dircmp.right_only])
    diff_files.extend([os.path.join(path, x) for x in dircmp.diff_files])
    for p, dir in dircmp.subdirs.iteritems():
      recurse(os.path.join(path, p), dir)
  
  recurse("", dircmp)

  if len(left_only) > 0:
    print "Removed files:"
    for p in left_only:
      print " - " + p

  if len(right_only) > 0:
    print "New files:"
    for p in right_only:
      print " + " + p

  if len(diff_files) > 0:
    print "Modified files:"
    for file_path in diff_files:
      # Use `U` mode in order to ignore different OS EOL
      sA = open(os.path.join(pathA, file_path), 'U').readlines()
      sB = open(os.path.join(pathB, file_path), 'U').readlines()
      line_added = 0
      line_deleted = 0
      for line in unified_diff(sA, sB, fromfile=zipA + "/" + file_path, tofile=zipB + "/" + file_path):
        if stat:
          if line[0] == '+':
            line_added += 1
          elif line[0] == '-':
            line_deleted += 1
        else:
          sys.stdout.write(line)
      if stat:
        print " * " + file_path + " ++(" + str(line_added) + ") --(" + str(line_deleted) + ")"

  if pathA != zipA:
    shutil.rmtree(pathA)
  shutil.rmtree(pathB)

# Unpack a given addon to `target` folder
def unpack(zip, version, manifest, target):
  if not os.path.isdir(target):
    raise Exception("`--target` options should be a path to an empty directory")
  if len(os.listdir(target)) > 0:
    raise Exception("Unable to unpack in an non-empty directory", target)
  packages = getPackages(manifest)

  packages.remove("addon-kit")
  packages.remove("api-utils")
  if len(packages) != 1:
    raise Exception("We are only able to unpack/repack addons without extra packages ", packages)
  os.mkdir(os.path.join(target, "lib"))
  os.mkdir(os.path.join(target, "data"))
  os.mkdir(os.path.join(target, "locale"))

  # Retrieve main package name
  package = packages[0]

  # Copy main package files
  for file, section, relpath in getPackagesFiles(zip, version, manifest, package):
    # Ignore tests folders
    if section in ["test", "tests"]:
      continue
    if not section in ["lib", "data"]:
      raise Exception("Unexpected section folder name: " + section)
    destFile = os.path.join(target, section, relpath)
    # We have to use zipinfo object in order to extract a file to a different
    # path, then we have to replace `\` in windows as zip only uses `/`
    info = zip.getinfo(file)
    info.filename = destFile.replace("\\", "/")
    zip.extract(info)

  # Copy locales
  for file in zip.namelist():
    # Ignore everything outside of locale folder, and folders
    if not file.startswith("locale/") or file[-1] == "/":
      continue
    langcode = os.path.splitext(os.path.basename(file))[0]
    locale = json.loads(zip.read(file))
    property = os.open(os.path.join(target, "locale", langcode + ".properties"), os.O_WRONLY | os.O_CREAT)
    for key, val in locale.items():
      if isinstance(val, unicode):
        str = key + u"=" + val + "\n"
        os.write(property, str.encode("utf-8"))
      # Handle plural forms which are dictionnary
      elif isinstance(val, dict):
        for rule, plural in val.items():
          str = key 
          # A special case for `other`, the generic form
          # SDK < 1.8 require a generic form. 
          # Newer versions accept having only plural form for all keys
          if rule != "other":
            str = str + u"[" + rule + u"]"
          str = str + u"=" + plural + "\n"
          os.write(property, str.encode("utf-8"))
      else:
        raise Exception("Unsupported locale value type: ", val)
    os.close(property)

  # Eventually copy icon files, may not exist so ignore any error
  try:
    info = zip.getinfo("icon.png")
    info.filename = os.path.join(target, "icon.png").replace("\\", "/")
    zip.extract(info)
  except:
    ()
  try:
    info = zip.getinfo("icon64.png")
    info.filename = os.path.join(target, "icon64.png").replace("\\", "/")
    zip.extract(info)
  except:
    ()

  # Recreate a package.json file
  metadata = manifest['metadata']
  if not package in metadata:
    raise Exception("Unable to find addon package in manifest's metadata field")
  packageMetadata = metadata[package]

  # `id` attribute isn't saved into metadata
  # A whitelist of attributes is used
  packageMetadata['id'] = manifest['jetpackID']

  # Nor `fullName` which is eventually used for install.rdf name
  rdf = zip.read('install.rdf')
  name = re.search("<em:name>(.+)<\/em:name>", rdf).group(1)
  if name != packageMetadata['name']:
    packageMetadata['fullName'] = name

  # preferences are hopefully copied to the manifest
  # we just have to copy them back to package.json
  if 'preferences' in manifest:
    packageMetadata['preferences'] = manifest['preferences']

  packageJson = os.open(os.path.join(target, "package.json"), os.O_WRONLY | os.O_CREAT)
  os.write(packageJson, json.dumps(packageMetadata, indent=2))
  os.close(packageJson)

  


import argparse

parser = argparse.ArgumentParser("SDK addons repacker",
  formatter_class=argparse.RawDescriptionHelpFormatter,
  description="Available actions:\n - `deps`: display dependencies used by the addon\n" +
              " - `checksum`: verify that the addon is only using official SDK files\n" +
              " - `unpack`: create a source package out of an \"compiled\" addon\n" +
              " - `repack`: rebuild an addon with another SDK version (need SDK `cfx` application)")
parser.add_argument("--batch", action="store_true", dest="batch",
                    help="Process `path` argument as a folder containing multiple addons")
parser.add_argument("--target", dest="target", default=os.path.dirname(__file__),
                    help="Folder where to put repacked xpi file(s)")
parser.add_argument("--force", action="store_true", dest="force", default=False,
                    help="Force unpack/repack even if checksums are wrong and addon are using a patched SDK version.")
parser.add_argument("--diff", action="store_true", dest="diff", default=False,
                    help="Print a diff between original XPI and repacked one.")
parser.add_argument("action", choices=["deps", "checksum", "unpack", "repack"],
                    help="Action to execute")
parser.add_argument("path",
                    help="path to either a xpi file or an extension folder to process")
args = parser.parse_args()

if args.action == "repack":
  try:
    subprocess.check_output("cfx --version", shell=True)
  except OSError, e:
    if e.errno == errno.ENOENT:
      print "Unable to run `cfx` application"
      print "Please install and setup cfx environnement"
      sys.exit()

if args.batch:
  for path in os.listdir(args.path):
    try:
      # Ignore already repacked addons
      if "-repacked" in path:
        continue
      if os.path.isdir(path) or os.path.splitext(path)[1] == "xpi":
        processAddon(path, args)
    except Exception, e:
      print "Unable to", args.action, path, ": ", e
else:
  processAddon(args.path, args)

