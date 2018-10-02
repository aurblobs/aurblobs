import json
import os
import sys
from tempfile import TemporaryDirectory
from shutil import rmtree

import datetime
import docker
import requests
from pkg_resources import parse_version

import click
from pretty_bad_protocol import gnupg

from .constants import CONFIG_DIR, CACHE_DIR, DOCKER_IMAGE, PROJECT_NAME
from .package import Package


class Repository:
    vcs_rebuild_age = 7 * 86400

    def __init__(self, name=None):
        try:
            self.name = name.lower()
        except AttributeError:
            self.name = None
        self.basedir = None
        self.packages = set()

        if name:
            self.load()

    def config_file(self):
        return os.path.join(CONFIG_DIR, '{0}.json'.format(self.name))

    def state_file(self):
        return os.path.join(CACHE_DIR, '{0}.json'.format(self.name))

    def signing_key_file(self):
        return os.path.join(CONFIG_DIR, '{0}.gpg'.format(self.name))

    def create(self, name, basedir, mail):
        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())

        self.name = name.lower()
        self.basedir = basedir

        # verify name is not taken
        if os.path.exists(self.config_file()) \
                or os.path.exists(self.state_file()):
            click.echo(
                'Repository with that name already exists',
                file=sys.stderr
            )
            sys.exit(1)

        # verify the basedir does not exist
        if os.path.exists(basedir):
            click.echo(
                'Basedir already exists',
                file=sys.stderr
            )
            sys.exit(1)

        # create basedir
        try:
            os.mkdir(basedir)
        except PermissionError:
            click.echo(
                'Unable to create basedir, no write permissions',
                file=sys.stderr
            )
            sys.exit(1)

        # create gpg signing key
        with TemporaryDirectory() as basedir:
            gpg = gnupg.GPG(homedir=basedir)
            gpg_version_string = gpg.binary_version.split('\\n')[0]

            # default to Ed25519, fallback to RSA for GPG versions before 2.1.0
            if parse_version(gpg_version_string) >= parse_version('2.1.0'):
                input_data = gpg.gen_key_input(
                    key_type='eddsa', key_length=521, key_curve='Ed25519',
                    key_usage='sign', expire_date=0, name_email=mail,
                    name_real='{0} repository key'.format(name),
                    testing=True  # don't protect the key
                )
            else:
                input_data = gpg.gen_key_input(
                    key_type='rsa', key_length=4096,
                    key_usage='sign', expire_date=0, name_email=mail,
                    name_real='{0} repository key'.format(name),
                    testing=True  # don't protect the key
                )

            key = gpg.gen_key(input_data)

            # copy public key to repository basedir
            with open(os.path.join(self.basedir, '{0}.gpg'.format(name)), 'w') as handle:
                handle.write(gpg.export_keys(key))

            # copy private key to config root
            with open(self.signing_key_file(), 'w') as handle:
                handle.write(gpg.export_keys(key, True))

        # initialize the empty repository
        volumes = {
            self.signing_key_file():
                {'bind': '/privkey.gpg', 'mode': 'ro'},
            self.basedir:
                {'bind': '/repo', 'mode': 'rw'},
        }

        client = docker.from_env()
        try:
            container = client.containers.run(
                image=DOCKER_IMAGE,
                entrypoint="/bin/sh -c "
                           "'usermod -u $USER_ID build && "
                           " su -c /init.sh build'",
                name='{0}_sign_{1}_{2}'.format(
                    PROJECT_NAME, self.name, timestamp),
                detach=True,
                environment={
                    "USER_ID": os.getuid(),
                    "REPO_NAME": self.name,
                },
                volumes=volumes,
                remove=True
            )
        except requests.exceptions.ConnectionError as ex:
            click.echo(
                'Unable to start container, is the docker daemon '
                'running?\n{0}'.format(ex),
                file=sys.stderr
            )
            sys.exit(1)

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

        if container.wait()['StatusCode'] == 0:
            # persist configuration
            self.save()
            click.echo(
                "Repository successfully initialized."
            )
        else:
            click.echo(
                "There were errors while initializing repository '{0}'.".format(self.name),
                file=sys.stderr
            )
            sys.exit(1)

    def drop(self):
        try:
            os.remove(self.config_file())
        except OSError as ex:
            click.echo(
                'Error while deleting configuration file at {0}: {1}'.format(
                    self.config_file(), ex),
                file=sys.stderr
            )

        try:
            os.remove(self.signing_key_file())
        except OSError as ex:
            click.echo(
                'Error while deleting signing key file at {0}: {1}'.format(
                    self.signing_key_file(), ex),
                file=sys.stderr
            )

        try:
            os.remove(self.state_file())
        except OSError as ex:
            click.echo(
                'Error while deleting state file at {0}: {1}'.format(
                    self.state_file(), ex),
                file=sys.stderr
            )

        try:
            rmtree(self.basedir)
        except OSError as ex:
            click.echo(
                'Error while deleting the repository at {0}: {1}'.format(
                    self.basedir, ex),
                file=sys.stderr
            )

    def load(self):
        try:
            with open(self.config_file()) as handle:
                config = json.load(handle)
        except FileNotFoundError:
            click.echo(
                '{0}: config file does not exist, exiting.'.format(self.name),
                file=sys.stderr
            )
            sys.exit(1)
        except json.decoder.JSONDecodeError as ex:
            click.echo(
                '{0}: config file is damaged, exiting. ({1})'.format(
                    self.name, ex),
                file=sys.stderr
            )
            sys.exit(1)

        try:
            with open(self.state_file()) as handle:
                state = json.load(handle)
        except FileNotFoundError:
            state = {}
            click.echo(
                '{0}: state file does not exist, assuming no state exists.'.format(
                    self.name
                ),
                file=sys.stderr
            )
        except json.decoder.JSONDecodeError as ex:
            click.echo(
                '{0}: state file is damaged, exiting. ({1}).'.format(
                    self.name, ex
                ),
                file=sys.stderr
            )
            sys.exit(1)

        self.basedir = config['basedir']

        for package in config['pkgs']:
            try:
                pkgstate = state['pkgs'][package]
            except KeyError:
                pkgstate = {}

            self.packages.add(
                Package(
                    repository=self,
                    name=package,
                    commit=pkgstate.get('commit', None),
                    pkgs=pkgstate.get('pkgs', None),
                    updated=pkgstate.get('updated', None)
                )
            )

    def save(self):
        class ConfigEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Package):
                    return o.name
                return json.JSONEncoder.default(self, o)

        # render config and state before opening their file for writing or else
        # there is a risk of truncation.
        config = {
            'basedir': self.basedir,
            'pkgs': list(self.packages)
        }

        state = {
            'pkgs': {
                pkg.name: {
                    'commit': pkg.commit,
                    'updated': pkg.updated,
                    'pkgs': {
                        pkgname: pkgver for pkgname, pkgver in pkg.pkgs.items()
                    }
                } for pkg in self.packages}
        }

        with open(self.config_file(), 'w') as handle:
            json.dump(config, handle, indent=2, cls=ConfigEncoder)

        with open(self.state_file(), 'w') as handle:
            json.dump(state, handle, indent=2)

    def add(self, pkgname):
        # check if pkg already configured
        for pkg in self.packages:
            if pkg.name == pkgname:
                click.echo(
                    '{0}: package {1} already configured'.format(
                        self.name, pkg.name),
                    file=sys.stderr
                )
                return
            elif pkgname in pkg.pkgs.keys():
                click.echo(
                    '{0}: package {1} is already configured as a part of {2}'.format(
                        self.name, pkgname, pkg.name),
                    file=sys.stderr
                )
                return

        # create package instance
        pkg = Package(self, pkgname)
        if not pkg.exists():
            click.echo(
                'package {0} does not exist in AUR'.format(pkg.name),
                file=sys.stderr
            )
            sys.exit(1)

        # add package to repository
        self.packages.add(pkg)
        self.save()

    def find_package(self, pkgname):
        try:
            return list(filter(
                lambda o: o.name == pkgname.lower(),
                self.packages)
            ).pop()
        except IndexError:
            click.echo(
                "Package {0} not found.".format(pkgname),
                file=sys.stderr
            )
            sys.exit(1)

    def sign_and_add(self, pkgroot):
        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())

        volumes = {
            pkgroot:
                {'bind': '/pkg', 'mode': 'rw'},
            self.signing_key_file():
                {'bind': '/privkey.gpg', 'mode': 'ro'},
            self.basedir:
                {'bind': '/repo', 'mode': 'rw'},
        }

        client = docker.from_env()
        try:
            container = client.containers.run(
                image=DOCKER_IMAGE,
                entrypoint="/bin/sh -c "
                           "'usermod -u $USER_ID build && "
                           " su -c /sign.sh build'",
                name='{0}_sign_{1}_{2}'.format(
                    PROJECT_NAME, self.name, timestamp),
                detach=True,
                environment={
                    "USER_ID": os.getuid(),
                    "REPO_NAME": self.name,
                },
                volumes=volumes,
                remove=True
            )
        except requests.exceptions.ConnectionError as ex:
            click.echo(
                'Unable to start container, is the docker daemon '
                'running?\n{0}'.format(ex),
                file=sys.stderr
            )
            sys.exit(1)

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

        return container.wait()['StatusCode'] == 0

    def remove_and_sign(self, pkgname):
        pkg = self.find_package(pkgname)

        # TODO: prompt y/N

        if not pkg.pkgs:
            self.packages.remove(pkg)
            self.save()
            click.echo(
                "{0}: package {1} successfully removed.".format(
                    self.name, pkgname)
            )
            sys.exit(0)

        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())
        volumes = {
            self.signing_key_file():
                {'bind': '/privkey.gpg', 'mode': 'ro'},
            self.basedir:
                {'bind': '/repo', 'mode': 'rw'},
        }

        client = docker.from_env()
        try:
            container = client.containers.run(
                image=DOCKER_IMAGE,
                entrypoint="/bin/sh -c "
                           "'usermod -u $USER_ID build && "
                           " su -c /remove.sh build'",
                name='{0}_sign_{1}_{2}'.format(
                    PROJECT_NAME, self.name, timestamp),
                detach=True,
                environment={
                    "USER_ID": os.getuid(),
                    "REPO_NAME": self.name,
                    "PKGNAMES": ' '.join(pkg.pkgs.keys())
                },
                volumes=volumes,
                remove=True
            )
        except requests.exceptions.ConnectionError as ex:
            click.echo(
                'Unable to start container, is the docker daemon '
                'running?\n{0}'.format(ex),
                file=sys.stderr
            )
            sys.exit(1)

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

        if container.wait()['StatusCode'] == 0:
            self.packages.remove(pkg)
            self.save()
            click.echo(
                "Package successfully removed."
            )
        else:
            click.echo(
                "There were errors while removing '{0}'.".format(pkgname),
                file=sys.stderr
            )
            sys.exit(1)
