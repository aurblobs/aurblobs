import json
import os
import sys
from tempfile import TemporaryDirectory

import gnupg
import click

from .constants import CONFIG_DIR, CACHE_DIR
from .package import Package


class Repository:
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
        self.name = name.lower()
        self.basedir = basedir

        # verify name is not taken
        if os.path.exists(self.config_file()) \
                or os.path.exists(self.state_file()):
            click.echo(
                'Repository with that name already exists',
                file=sys.stderr
            )
            return

        # verify the basedir does not exist
        if os.path.exists(basedir):
            click.echo(
                'Basedir already exists',
                file=sys.stderr
            )
            return

        # verify we can write to roots parent
        if not os.access(os.path.join(basedir, '..'), os.W_OK):
            click.echo(
                'Unable to create basedir, no write permissions.',
                file=sys.stderr
            )

        # create basedir
        os.mkdir(basedir)

        # create gpg signing key
        with TemporaryDirectory() as basedir:
            gpg = gnupg.GPG(homedir=basedir)
            input_data = gpg.gen_key_input(
                key_type='eddsa', key_length=521, key_curve='Ed25519',
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

        # persist configuration
        self.save()

    def load(self):
        click.echo(
            "loading config: {0}".format(self.config_file()),
            file=sys.stderr
        )
        with open(self.config_file()) as handle:
            config = json.load(handle)

        click.echo(
            "loading state: {0}".format(self.state_file()),
            file=sys.stderr
        )
        with open(self.state_file()) as handle:
            state = json.load(handle)

        self.basedir = config['basedir']

        for package in config['pkgs']:
            try:
                pkgstate = state['pkgs'][package]
            except KeyError:
                pkgstate = None

            self.packages.add(
                Package(
                    repository=self,
                    name=package,
                    commit=pkgstate['commit'] if pkgstate else None,
                    pkgs=pkgstate['pkgs']
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
                    'package already configured',
                    file=sys.stderr
                )
                return
            elif pkgname in pkg.pkgs.keys():
                click.echo(
                    'package is already configured as a part of pkg "{0}"'.format(pkgname),
                    file=sys.stderr
                )
                return

        # create package instance
        pkg = Package(self, pkgname)
        print(pkg)

        # add package to repository
        self.packages.add(pkg)
        self.save()

    def remove(self, pkgname):
        pkg = list(filter(
            lambda o: o.name == pkgname.lower(),
            self.packages)
        ).pop()

        if not pkg:
            click.echo("package not found", file=sys.stderr)
            return

        # TODO: implement package removal
        click.echo('Implementation missing', file=sys.stderr)
        # prompt y/N
        # repo-remove
        # remove from config & state
        # save
