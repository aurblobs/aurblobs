#! /bin/bash

gpg --import /privkey.gpg

cd /pkg
makepkg -fs --noconfirm --sign

if [ $? -eq 0 ]; then
	echo "Build succeded. Update repository db"

	cd /repo
	cp /pkg/*.pkg.tar.xz .
	cp /pkg/*.pkg.tar.xz.sig .
	repo-add $REPO_NAME.db.tar.gz *.pkg.tar.xz
else
	echo "Build process failed"
fi


