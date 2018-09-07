import datetime
import os
import sys
import tarfile
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import docker
import git
import requests

from .constants import PROJECT_NAME, DOCKER_IMAGE, PACMAN_SYNC_CACHE_DIR


class Package:
    def __init__(self, repository, name, commit=None, updated=None, pkgs=None):
        # back-reference to the repository this package is being served in
        self.repository = repository

        # name and known git commit hash of the AUR package
        self.name = name
        self.commit = commit
        self.updated = updated

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

    def is_vcs(self):
        return self.name.endswith((
            '-cvs', '-svn', '-git', '-hg', '-bzr', '-darcs'
        ))

    def needs_rebuild(self, head, force=False):
        if force:
            return True
        if self.commit != head:
            click.echo('{0}: PKGBUILD updated from {1} to {2}'.format(
                self.fullname, self.commit, head
            ))
            return True
        if self.is_vcs():
            if not self.updated:
                click.echo(
                    '{0}: rebuilding vcs package due to missing build '
                    'timestamp.'.format(self.fullname)
                )
                return True
            pkg_age = (int(time.time()) - self.updated)
            if pkg_age >= self.repository.vcs_rebuild_age:
                click.echo(
                    '{0}: regularly rebuild for vcs package triggered'.format(
                        self.fullname
                    )
                )
                return True
        click.echo('{0} is up-to-date'.format(self.fullname))
        return False

    def update(self, buildopts=None, force=False):
        if not buildopts:
            buildopts = {}

        head = git.cmd.Git().ls_remote(self.aur_git_url(), "HEAD").split()[0]
        if not self.needs_rebuild(head, force):
            return False

        with TemporaryDirectory(prefix=PROJECT_NAME, suffix=self.name) as basedir:
            pkgroot = os.path.join(basedir, '{0}.git'.format(self.name))
            pkgrepo = git.Repo.clone_from(
                self.aur_git_url(), pkgroot
            )

            head = str(pkgrepo.head.commit)
            buildopts['pkgroot'] = pkgroot
            if self.build(**buildopts):
                click.echo(
                    '{0}: package build complete'.format(self.fullname)
                )

                self.repository.sign_and_add(pkgroot)
                click.echo(
                    '{0}: package signed and repository updated'.format(
                        self.fullname
                    )
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
                self.updated = int(time.time())
                self.pkgs = resulting_pkgs
            else:
                click.echo(
                    '{0}: build unsuccessful check the build log for '
                    'errors.'.format(self.fullname),
                    file=sys.stderr
                )

        return False

    def build(self, pkgroot, pkgcache=None, jobs=None):
        click.echo('{0}: starting build'.format(self.fullname))

        timestamp = '{:%H-%M-%s}'.format(datetime.datetime.now())

        volumes = {
            pkgroot:
                {'bind': '/pkg', 'mode': 'rw'},
            self.repository.basedir:
                {'bind': '/repo', 'mode': 'ro'},
            PACMAN_SYNC_CACHE_DIR:
                {'bind': '/var/lib/pacman/sync', 'mode': 'rw'},
        }

        if pkgcache:
            volumes[pkgcache] = {'bind': '/var/cache/pacman/pkg', 'mode': 'rw'}

        client = docker.from_env()
        try:
            container = client.containers.run(
                image=DOCKER_IMAGE,
                command="/bin/sh -c "
                        "'usermod -u $USER_ID build &&"
                        " su -c /build.sh build'",
                name='{0}_build_{1}_{2}'.format(
                    PROJECT_NAME, self.name, timestamp),
                detach=True,
                environment={
                    "USER_ID": os.getuid(),
                    "JOBS": jobs or os.cpu_count(),
                    "REPO_NAME": self.repository.name,
                },
                volumes=volumes,
                remove=True
            )
        except requests.exceptions.ConnectionError as ex:
            click.echo(
                'Unable to start container, is the docker daemon running?\n'
                '{0}'.format(ex),
                file=sys.stderr
            )
            sys.exit(1)

        for line in container.logs(stream=True):
            print('\t{0}'.format(line.decode().rstrip('\n')))

        return container.wait()['StatusCode'] == 0

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
