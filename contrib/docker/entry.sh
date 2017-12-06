#!/bin/bash

set -e

gpg --import /privkey.gpg

cd /pkg
makepkg -fs --noconfirm --sign

if [ $? -eq 0 ]; then
	echo "Build succeded. Update repository db"

	cd /repo
	cp /pkg/*.pkg.tar.* .
	repo-add --delta --remove $REPO_NAME.db.tar.gz $(ls /pkg/*.pkg.tar.xz)

	exit 0
else
	exit 1
fi


