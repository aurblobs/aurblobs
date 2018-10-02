#!/bin/bash

set -e

gpg --import /privkey.gpg

cd /repo
repo-remove --sign $REPO_NAME.db.tar.gz $PKGNAMES

exit 0
