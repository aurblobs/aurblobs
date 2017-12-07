import datetime
import os
import tarfile
import sys
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

    @property
    def fullname(self):
        return '{0}/{1}'.format(self.repository.name, self.name)

    def aur_pkg_url(self):
        return 'https://aur.archlinux.org/packages/{0}/'.format(self.name)

    def aur_git_url(self):
        return 'https://aur.archlinux.org/{0}.git'.format(self.name)

    def exists(self):
        return requests.head(self.aur_pkg_url()).status_code != 404

    def is_new(self, commit):
        # we can only compare git hashes of the repository, a new version
        # string might be determined at build time
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
                    click.echo('{0}: PKGBUILD updated from {1} to {2}'.format(
                        self.fullname, self.commit, head
                    ))

                if self.build(pkgroot):
                    click.echo(
                        '{0}: package build complete'.format(self.fullname)
                    )

                    resulting_pkgs = self.get_pkg_names(pkgroot)

                    # show new packages, that did not exist before
                    new = [pkgname for pkgname in resulting_pkgs.keys()
                           if pkgname not in self.pkgs]
                    if new:
                        click.echo('  new:')
                        for pkgname in new:
                            click.echo('    - {0} ({1})'.format(
                                pkgname, resulting_pkgs[pkgname]['version']
                            ))

                    # show upgraded packages, where the version string changed
                    upgraded = [
                        pkgname for pkgname, pkginfo in resulting_pkgs.items()
                        if pkgname in self.pkgs
                        and self.pkgs[pkgname]['version'] != pkginfo['version']
                    ]
                    if upgraded:
                        click.echo('  upgraded:')
                        for pkgname in upgraded:
                            click.echo('    - {0} ({1} → {2})'.format(
                                pkgname,
                                self.pkgs[pkgname]['version'],
                                resulting_pkgs[pkgname]['version'],
                            ))

                    # show old packages that were not rebuilt
                    # TODO: remove these packages from the repository
                    dangling = [
                        pkgname for pkgname in self.pkgs.keys()
                        if pkgname not in resulting_pkgs
                    ]
                    if dangling:
                        click.echo('  dangling:')
                        for pkgname in dangling:
                            click.echo(
                                '    - {0} ({1}): {2}'.format(
                                    pkgname,
                                    self.pkgs[pkgname]['version'],
                                    self.pkgs[pkgname]['file']
                                )
                            )

                    self.commit = head
                    self.pkgs = resulting_pkgs
                else:
                    click.echo(
                        '{0}: build unsuccessful check the build log for '
                        'errors.'.format(self.fullname),
                        file=sys.stderr
                    )

            else:
                click.echo('{0} is up-to-date'.format(self.fullname))

        return False

    def build(self, pkgroot):
        signing_key = self.repository.signing_key_file()
        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())

        click.echo('{0}: starting build'.format(self.fullname))

        client = docker.from_env()
        # remove=True only removed for debugging purposes in this early stage.
        try:
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
        except requests.exceptions.ConnectionError as ex:
            click.echo(
                'Unable to start build container, is the docker daemon '
                'running?\n{0}'.format(ex),
                file=sys.stderr
            )
            sys.exit(1)

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

        return container.wait() == 0

    @staticmethod
    def get_pkg_names(pkgroot):
        def pkgname_from_pkgfile(pkgfile):
            # open pkg.tar.* file and read metadata from .PKGINFO file
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
            pkgfile = str(pkgfile)

            if pkgfile.endswith('.sig'):
                # skip signature files
                continue

            pkgname, pkgver = pkgname_from_pkgfile(pkgfile)
            resulting_pkgs[pkgname] = {
                'version': pkgver,
                'file': os.path.basename(pkgfile)
            }

        return resulting_pkgs
