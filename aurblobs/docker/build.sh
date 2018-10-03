#!/bin/bash

set -e

# https://bugs.archlinux.org/task/50439
fix_makepkg_chmod() {
    chmod a+rw /pkg/pkg
}

trap fix_makepkg_chmod EXIT

cat << EOF | sudo tee --append /etc/pacman.conf
[${REPO_NAME}]
SigLevel = Never
Server = file:///repo
EOF

sudo pacman -Sy

cd /pkg

# import gpg keys if necessary
(source PKGBUILD;
 if [ ! -z $validpgpkeys ]; then
        gpg --recv-keys $validpgpkeys
 fi)

makepkg -fs --noconfirm MAKEFLAGS=-j$JOBS

exit 0
