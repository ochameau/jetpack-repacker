#!/bin/sh

git ls-remote -t http://github.com/mozilla/addon-sdk "refs/tags/[1-9].*" | sed 's:.*/::'
