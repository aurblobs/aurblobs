import datetime
import os
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import docker
import git
import requests

from .constants import PROJECT_NAME, DOCKER_IMAGE


class Package:
    def __init__(self, repository, name, commit=None, pkgs=None):
        # back-reference to the repository this package is being served in
        self.repository = repository

        # name and known git commit hash of the AUR package
        self.name = name
        self.commit = commit

        # map of packages & package versions created during the build process
        if not pkgs:
            pkgs = {}
        self.pkgs = pkgs

    def __hash__(self):
        # deduplicate packages by name
        return hash(self.name)

    def aur_pkg_url(self):
        return 'https://aur.archlinux.org/packages/{0}/'.format(self.name)

    def aur_git_url(self):
        return 'https://aur.archlinux.org/{0}.git'.format(self.name)

    def exists(self):
        return requests.head(self.aur_pkg_url()).status_code != 404

    def is_new(self, commit):
        # we can only compare git hashes of the repository, a new version string
        # might be determined at build time
        return self.commit != commit

    def update(self, force=False):
        with TemporaryDirectory(prefix=PROJECT_NAME, suffix=self.name) as basedir:
            pkgroot = os.path.join(basedir, '{0}.git'.format(self.name))
            pkgrepo = git.Repo.clone_from(
                self.aur_git_url(), pkgroot
            )

            head = str(pkgrepo.head.commit)
            if force or self.is_new(head):
                if self.commit != head:
                    click.echo('{0} PKGBUILD updated from {1} to {2}'.format(
                        self.name, self.commit, head
                    ))

                self.build(pkgroot)
                self.commit = head

                new_pkgs = self.get_pkg_names(pkgroot)
                if not self.pkgs:
                    pkgdiff = set(new_pkgs.keys()).difference(set(self.pkgs.keys()))
                    if pkgdiff:
                        click.echo('package {0} did not update [{1}]'.format(
                            self.name, ', '.join(pkgdiff)
                        ))

                print("old", self.pkgs)
                self.pkgs = new_pkgs
                print("new", self.pkgs)

            else:
                click.echo('{0} is up-to-date'.format(self.name))

        return False

    def build(self, pkgroot):
        signing_key = self.repository.signing_key_file()
        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())

        click.echo('Building {0}...'.format(self.name))

        client = docker.from_env()
        # remove=True only removed for debugging purposes in this early stage.
        container = client.containers.run(
            image=DOCKER_IMAGE,
            name='{0}_{1}_{2}'.format(PROJECT_NAME, self.name, timestamp),
            detach=True,
            environment={
                "REPO_NAME": self.repository.name,
                "USER_ID": os.getuid()
            },
            volumes={
                pkgroot: {'bind': '/pkg', 'mode': 'rw'},
                self.repository.basedir: {'bind': '/repo', 'mode': 'rw'},
                signing_key: {'bind': '/privkey.gpg', 'mode': 'ro'}
            }
        )

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

    @staticmethod
    def get_pkg_names(pkgroot):
        def pkgname_from_pkgfile(pkgfile):
            # open pkg.tar.* file and read metadata from .PKGINFO file
            print(pkgfile, os.path.exists(pkgfile))
            with tarfile.open(pkgfile, 'r') as tar:
                # find pkgname and pkgver
                with TemporaryDirectory(prefix='srcinfo') as tempdir:
                    tar.extract('.PKGINFO', tempdir)
                    with open(os.path.join(tempdir, '.PKGINFO')) as handle:
                        pkgname = pkgver = None
                        for line in handle.readlines():
                            try:
                                k, v = line.split('=')
                                k = k.strip()
                                v = v.strip()
                            except ValueError:
                                continue

                            if k == 'pkgname':
                                pkgname = v
                            elif k == 'pkgver':
                                pkgver = v
                        return pkgname, pkgver

        # use globbing to find packages in pkgroot
        resulting_pkgs = {}
        for pkgfile in Path(pkgroot).glob('*.pkg.tar*'):
            if str(pkgfile).endswith('.sig'):
                # skip signature files
                continue

            pkgname, pkgver = pkgname_from_pkgfile(str(pkgfile))
            resulting_pkgs[pkgname] = {
                'version': pkgver,
                'file': os.path.basename(pkgfile)
            }

        return resulting_pkgs
