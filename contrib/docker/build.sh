#!/bin/bash

set -e

sudo pacman -Sy

cd /pkg

# import gpg keys if necessary
(source PKGBUILD;
 if [ ! -z $validpgpkeys ]; then
        gpg --recv-keys $validpgpkeys
 fi)

makepkg -fs --noconfirm MAKEFLAGS=-j$JOBS

exit 0
