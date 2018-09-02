#!/bin/bash

set -e

gpg --import /privkey.gpg

cd /repo

repo-add --sign --remove $REPO_NAME.db.tar.gz

exit 0
