#!/usr/bin/env python
import os, re
from sys import stdout, stderr
from os.path import join, abspath, isfile, isdir, exists, basename
from shutil import copyfile, copytree, rmtree
from time import strftime, strptime, localtime
import urllib2
import MySQLdb as mdb
import sys
from yaml import load, dump

# speedy YAML
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

con = None
config_file = './amo_db_config.yml'
download_dir = abspath('./xpis')

def getYaml(path):
    """ loadin' YAML files. """
    if not exists(path):
        raise Exception("YAML file doesn't exist: %s" % path)
    return load(file(path, 'r'), Loader)


def download(id, filename, download_dir, i, total_rows):
    """ relatively simple binary downloader 
        no fancy features like following redirects, etc.
    """
    url_tpl = 'https://addons.cdn.mozilla.net/storage/public-staging/%d/%s'

    remote = url_tpl % (id, filename)
    local = join(download_dir, filename)

    # return errors...
    stdout.write("(%d/%d) Downloading %s" % (i, total_rows, filename))
    stdout.flush()
    try:
        u = urllib2.urlopen(remote)
    except urllib2.HTTPError, e:
        reason = ''
        if hasattr(e, 'reason'):
            reason = e.reason
        stderr.write("ERR %s %s: %s %s\n" % ( e.code, reason, id, filename ))
        stderr.flush()
	return

    h = u.info()
    totalSize = int(h["Content-Length"])
    stdout.write(" fetching %skb " % (totalSize / 1024))
    stdout.flush()

    fp = open(local, 'wb')

    blockSize = 8192 #100000 # urllib.urlretrieve uses 8192
    count = 0
    str_init = "0%"
    width = len(str_init)
    stdout.write(str_init)
    stdout.flush()

    while True:
        chunk = u.read(blockSize)
        if not chunk: break
        fp.write(chunk)
        count += 1
        if totalSize > 0:
            percent = int(count * blockSize * 100 / totalSize)
            if percent > 100: percent = 100
            back = "\b" * width
            stdout.write(back)
            str_pct = "%d%%" % percent
            stdout.write(str_pct)
            stdout.flush()
            width = len(str_pct)

    fp.flush()
    fp.close()
    stdout.write(" Done.\n")
    stdout.flush()

if __name__ == '__main__':
    # database connection.
    dbConfig = getYaml(config_file)

    if not exists(download_dir):
        os.mkdir(download_dir)

    errors = []

    try:
        # con = mdb.connect('localhost', 'testuser', 
        #     'test623', 'testdb');

        con = mdb.connect(dbConfig['host'],
            dbConfig['user'],
            dbConfig['password'],
            dbConfig['database'],
        );

        path = os.path.join(os.path.dirname(__file__), 'queries.yml')
        queries = getYaml(path)

        cur = con.cursor()
        # repack_query_limit
        # cur.execute(queries['repack_query_limit'])
        cur.execute(queries['repack_query'])

        rows = cur.fetchall()
        
        i = 0
        total_rows = len(rows)

        print "Downloading %d extensions, hold on." % total_rows

        for r in rows:
            filename = r[5]
            id = r[0]
            i += 1
            if not exists(join(download_dir, filename)):
                download(id, filename, download_dir, i, total_rows)
            else:
                print "File already exists: %s" % filename
    except mdb.Error, e:
      
        stderr.write("Error %d: %s\n" % (e.args[0],e.args[1]))
        sys.exit(1)
        
    finally:    
        if con:
            con.close()

