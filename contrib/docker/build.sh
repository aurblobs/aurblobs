#!/bin/bash

set -e

sudo pacman -Sy

cd /pkg
makepkg -fs --noconfirm MAKEFLAGS=-j$JOBS

exit 0
