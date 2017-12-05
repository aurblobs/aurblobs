import os.path
import sys
from pathlib import Path

import click

from . import __VERSION__
from .constants import CONFIG_DIR, CACHE_DIR, PROJECT_NAME
from .repository import Repository

for directory in [CONFIG_DIR, CACHE_DIR]:
    try:
        os.mkdir(directory)
    except FileExistsError:
        pass

available_repositories = [os.path.basename(str(fn)).split('.')[:-1][0]
                          for fn in Path(CONFIG_DIR).glob('*.json')]


def is_valid_repository(ctx, param, value):
    if value and value not in available_repositories:
        click.echo('Repository with that name does not exist', file=sys.stderr)
        sys.exit(1)


@click.group()
@click.version_option(prog_name=PROJECT_NAME, version=__VERSION__)
def cli():
    pass


@click.command(short_help='Initialize a new repository.')
@click.argument('repository')
@click.argument('basedir')
@click.argument('mail')
def init(repository, basedir, mail):
    repo = Repository()

    repo.create(repository, basedir, mail)


@click.command(short_help='Add a new package to an existing repository.')
@click.option('--repository', default=None, callback=is_valid_repository)
@click.argument('package')
def add(repository, package):
    if not repository:
        if len(available_repositories) != 1:
            click.echo(
                "Repository ambiguous, specify one with --repository.",
                file=sys.stderr
            )
            sys.exit(1)
        repository = available_repositories[0]

    repo = Repository(repository)

    repo.add(package)


@click.command(short_help='Remove a package from a repository')
@click.option('--repository', callback=is_valid_repository)
@click.argument('package')
def remove(repository, package):
    repo = Repository(repository)

    repo.remove(package)


@click.command('list', short_help='List repositories and related packages')
@click.option('--repository', callback=is_valid_repository)
def _list(repository=None):
    if repository:
        repositories = [Repository(repository)]
    else:
        repositories = available_repositories

    for name in repositories:
        repository = Repository(name)

        click.echo("{0}: {1} ({2} packages)".format(
            repository.name, repository.basedir, len(repository.packages)))

        for package in repository.packages:
            if not package.pkgs:
                click.echo(' - {0} (not built yet)'.format(package.name))
            elif len(package.pkgs) == 1 and package.name in package.pkgs:
                click.echo(' - {0} ({1})'.format(
                    package.name, package.pkgs[package.name]['version']))
            else:
                click.echo(' - {0}'.format(package.name))
                for _package in package.pkgs:
                    click.echo('   - {0}'.format(_package))


@click.command(short_help='Update packages in repository to latest version.')
@click.option('--repository', default=None, callback=is_valid_repository)
@click.option('--force', is_flag=True, default=False,
              help='Bypass up-to-date check')
def update(repository, force):
    if repository:
        repositories = [Repository(repository)]
    else:
        repositories = available_repositories

    for name in repositories:
        repository = Repository(name)

        for pkg in repository.packages:
            pkg.update(force)
            repository.save()


cli.add_command(init)
cli.add_command(add)
cli.add_command(remove)
cli.add_command(_list)
cli.add_command(update)


if __name__ == '__main__':
    cli()
