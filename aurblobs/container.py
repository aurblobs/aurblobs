import os
import sys

import click
import docker
from docker.errors import BuildError, APIError, ImageNotFound

from .constants import DOCKER_IMAGE, DOCKER_BASE_IMAGE


def need_rebuild():
    client = docker.from_env()

    # base image does not exist
    try:
        baseimage = client.images.get(DOCKER_BASE_IMAGE)
    except ImageNotFound:
        click.echo(
            'Build container rebuild necessary: base layer missing'
        )
        return True

    # base image outdated
    baseimage_new = client.images.pull(DOCKER_BASE_IMAGE)
    if baseimage.id != baseimage_new.id:
        click.echo(
            'Build container rebuild necessary: base layer update available'
        )
        return True

    # build image does not exist
    try:
        image = client.images.get(DOCKER_IMAGE)
    except ImageNotFound:
        click.echo(
            'Image for build container not found, need to build it'
        )
        return True

    # most recent base layer is missing in build image
    baselayer_found = False
    for layer in image.history():
        if layer['Id'] == "<missing>":
            continue
        if layer['Id'].split(':', 1)[1].startswith(baseimage_new.id):
            baselayer_found = True
            break

    if not baselayer_found:
        click.echo(
            'Build container rebuild required: base layer update available'
        )
        return True

    # build image outdated
    if DOCKER_IMAGE not in image.tags:
        click.echo(
            'Build container rebuild required: matching tag was not found'
        )
        return True

    return False


def update_build_container():
    if not need_rebuild():
        return

    client = docker.from_env()
    try:
        image, response = client.images.build(
            path=os.path.join(os.path.dirname(__file__), 'docker'),
            tag=DOCKER_IMAGE,
            pull=True,
        )

        click.echo('Image {image} updated'.format(image=image.tags[0]))

    except BuildError as ex:
        click.echo('Error while building the container: {}'.format(ex))
        sys.exit(1)
    except APIError as ex:
        click.echo('Error communicating with your docker daemon: {}'.format(ex))
        sys.exit(2)
