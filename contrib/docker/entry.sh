#!/bin/bash

gpg --import /privkey.gpg

cd /pkg
makepkg -fs --noconfirm --sign

if [ $? -eq 0 ]; then
	echo "Build succeded. Update repository db"

	cd /repo
	mkdir -p pkgs
	cp /pkg/*.pkg.tar.xz pkgs/
	cp /pkg/*.pkg.tar.xz.sig pkgs/
	repo-add --delta --remove $REPO_NAME.db.tar.gz pkgs/*.pkg.tar.xz

	exit 0
else
	exit 1
fi


