import os
import xdg

from . import __PROJECT__ as PROJECT_NAME

CONFIG_DIR = os.path.join(xdg.XDG_CONFIG_HOME, PROJECT_NAME)
CACHE_DIR = os.path.join(xdg.XDG_CACHE_HOME, PROJECT_NAME)

DOCKER_IMAGE = '{0}-build'.format(PROJECT_NAME)
