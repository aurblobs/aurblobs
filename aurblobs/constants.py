import os
from xdg.BaseDirectory import xdg_config_home, xdg_cache_home

from . import __PROJECT__ as PROJECT_NAME

CONFIG_DIR = os.path.join(xdg_config_home, PROJECT_NAME)
CACHE_DIR = os.path.join(xdg_cache_home, PROJECT_NAME)

PACMAN_SYNC_CACHE_DIR = os.path.join(CACHE_DIR, 'sync')

DOCKER_IMAGE = 'aurblobs/build'
