#!/bin/bash

set -e

gpg --import /privkey.gpg

cd /pkg

PKGS=$(basename -a `ls /pkg/*.pkg.tar.xz` | tr '\n' ' ')

# sign packages
for PKG in $PKGS; do
    gpg --detach-sign --no-armor $PKG
done

cd /repo
cp /pkg/*.pkg.tar.* .

repo-add --sign --delta --remove $REPO_NAME.db.tar.gz $PKGS

exit 0
