import os
import xdg

from . import __PROJECT__ as PROJECT_NAME

CONFIG_DIR = os.path.join(xdg.XDG_CONFIG_HOME, PROJECT_NAME)
CACHE_DIR = os.path.join(xdg.XDG_CACHE_HOME, PROJECT_NAME)

PACMAN_SYNC_CACHE_DIR = os.path.join(CACHE_DIR, 'sync')

DOCKER_IMAGE = 'aurblobs/build'
