from pathlib import Path

import click
import os.path

from . import __VERSION__
from .constants import CONFIG_DIR, PROJECT_NAME
from .repository import Repository


@click.group()
@click.version_option(prog_name=PROJECT_NAME, version=__VERSION__)
def cli():
    pass


@click.command(short_help='Initialize a new repository.')
@click.argument('repository')
@click.argument('basedir')
@click.argument('mail')
def init(repository=None, basedir=None, mail=None):
    repo = Repository()

    repo.create(repository, basedir, mail)


@click.command(short_help='Add a new package to an existing repository.')
@click.argument('repository')
@click.argument('package')
def add(repository=None, package=None):
    repo = Repository(repository)

    repo.add(package)


@click.command(short_help='Remove a package from a repository')
@click.argument('repository')
@click.argument('package')
def remove(repository, package):
    repo = Repository(repository)

    repo.remove(package)


@click.command('list', short_help='List repositories and related packages')
@click.argument('repository', default=False)
def _list(repository):
    if not repository:
        repositories = [
            Repository('.'.join(os.path.basename(repofile).split('.')[:-1]))
            for repofile
            in Path(CONFIG_DIR).glob('*.json')
        ]
    else:
        repositories = [Repository(repository)]

    for repository in repositories:
        click.echo("{0}: {1} ({2} packages)".format(
            repository.name, repository.basedir, len(repository.packages)))

        for package in repository.packages:
            if not package.pkgs:
                click.echo(' - {0} (not built yet)'.format(package.name))
            elif len(package.pkgs) == 1:
                click.echo(' - {0} ({1})'.format(
                    package.name, package.pkgs[package.name]))
            else:
                click.echo(' - {0}'.format(package.name))
                for _package in package.pkgs:
                    click.echo('   - {0}'.format(_package))


@click.command(short_help='Update packages in repository to latest version.')
@click.argument('repository')
@click.option('--force', is_flag=True, default=False,
              help='Bypass up-to-date check')
def update(repository, force):
    repo = Repository(repository)

    for pkg in repo.packages:
        pkg.update(force)
        repo.save()


cli.add_command(init)
cli.add_command(add)
cli.add_command(remove)
cli.add_command(_list)
cli.add_command(update)


if __name__ == '__main__':
    cli()