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
with codecs.open(os.path.join(here, 'README.rst'), encoding='utf-8') as handle:
    long_description = handle.read()

# required dependencies
required = [
    'click',
    'docker>=3.0.0',
    'GitPython',
    'pretty-bad-protocol>=3.1.1',
    'requests',
    'pyxdg'
]


setup(
    name='aurblobs',
    version=__VERSION__,
    description='Automatically build AUR packages and serve them from a '
                'repository',
    long_description=long_description,
    author='Martin Weinelt',
    author_email='martin+aurblobs@linuxlounge.net',
    url='https://www.github.com/aurblobs/aurblobs',
    license='AGPL',
    install_requires=required,
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(),
    entry_points={
        'console_scripts': ['aurblobs=aurblobs.__main__:cli']
    },
)
