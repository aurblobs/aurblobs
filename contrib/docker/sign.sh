#!/bin/bash

set -e

gpg --import /privkey.gpg

cd /repo
cp /pkg/*.pkg.tar.* .
repo-add --sign --delta --remove $REPO_NAME.db.tar.gz $(basename -a `ls /pkg/*.pkg.tar.xz` | tr '\n' ' ')

exit 0
