import codecs
import os.path

import sys
from setuptools import setup, find_packages

from aurblobs import __VERSION__


if sys.argv[-1] == "publish":
    os.system("python setup.py sdist bdist_wheel upload")
    sys.exit()

here = os.path.abspath(os.path.dirname(__file__))


# use README as long description
with codecs.open(os.path.join(here, 'README.md'), encoding='utf-8') as handle:
    long_description = handle.read()

# required dependencies
required = [
    'click',
    'docker',
    'GitPython',
    'gnupg',
    'requests',
    'xdg'
]


setup(
    name='aurblobs',
    version=__VERSION__,
    description='Automatically build AUR packages and serve them from a '
                'repository',
    long_description=long_description,
    author='Martin Weinelt',
    author_email='martin+aurblobs@linuxlounge.net',
    url='https://www.github.com/mweinelt/aurblobs',
    license='AGPL',
    install_requires=required,
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': ['aurblobs=aurblobs:cli']
    },
)
