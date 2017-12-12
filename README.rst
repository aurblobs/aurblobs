aurblobs
========

Automatically build AUR packages and serve them from a repository

Installation
------------

The latest release can be installed from PyPi:

::

    $ pip install aurblobs

and upgraded with:

::

    $ pip install --upgrade aurblobs


Dependencies
------------

- Docker
- GnuPG
    - versions >=2.1.0 will generate Ed25519 Signing Keys
    - older versions will generate RSA (4096 Bit) Signing Keys


Usage
-----

::

    Usage: aurblobs [OPTIONS] COMMAND [ARGS]...

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      add     Add a new package to an existing repository.
      init    Initialize a new repository.
      list    List repositories and related packages
      remove  Remove a package from a repository
      update  Update packages in repository to latest version.


Initializing repository
/////////////////////

This will create the repository basedir and a dedicatd GPG keypair. It will also install
the public key into the basedir.

::

    $ aurblobs init myrepo /srv/www/myrepo myrepo@example.com


Adding a package
////////////////

Adding a new package to a repository validates its existence on AUR and configures it to be built on the next update
run.

::

    $ aurblobs add youtube-dl-git


If multiple repositories are set up the specific repository must be specified:

::

    $ aurblobs add --repository myrepo youtube-dl-git


Listing configured repositories and packages
////////////////////////////////////////////

::

    $ aurblobs list
    myrepo: /srv/www/myrepo (3 packages)
     - dino-git (r214.dc2dde5-1)
     - youtube-dl-git (2017.12.02.r7.b271e3352-1)
     - tinc-pre-git (1.1pre15.21.gb8acb89a-1)


Building packages
/////////////////

With the update command all configured repositories and packages can be checked for
updates. If updates for a package are available it will be rebuilt in a container, with
a minimal Arch Linux build environment.
The build container will be pulled from the Docker Hub just before the first build is started.

::

    % aurblobs update --repository myrepo
    youtube-dl-git is up-to-date
    dino-git is up-to-date
    tinc-pre-git is up-to-date


Sharing the repository
//////////////////////

The repository basedir should then be exposed via a webserver.

::

    $ tree /srv/www/myrepo
    /srv/www/myrepo
    ├── myrepo.db -> myrepo.db.tar.gz
    ├── myrepo.db.tar.gz
    ├── myrepo.db.tar.gz.old
    ├── myrepo.files -> myrepo.files.tar.gz
    ├── myrepo.files.tar.gz
    ├── myrepo.files.tar.gz.old
    ├── myrepo.gpg
    ├── dino-git-r214.dc2dde5-1-x86_64.pkg.tar.xz
    ├── dino-git-r214.dc2dde5-1-x86_64.pkg.tar.xz.sig
    ├── tinc-pre-git-1.1pre15.21.gb8acb89a-1-any.pkg.tar.xz
    ├── tinc-pre-git-1.1pre15.21.gb8acb89a-1-any.pkg.tar.xz.sig
    ├── youtube-dl-git-2017.12.02.r8.3c4fbfeca-1-any.pkg.tar.xz
    └── youtube-dl-git-2017.12.02.r8.3c4fbfeca-1-any.pkg.tar.xz.sig


Configuring the repository locally
//////////////////////////////////

Download and import the repositories signing key into your truststore.

::

    # wget https://example.com/myrepo/myrepo.gpg
    # pacman-key --add myrepo.gpg


Lookup the key fingerprint:

::

    # pacman-key --list-keys | grep -B2 "prebuilt repository key"
    pub   ed25519 2017-12-04 [SCA]
          6E688777E2795B67C578EF3591149FE64075FE41
    uid           [  full  ] prebuilt repository key (insecure!) <myrepo@example.com>


And sign the key locally:

::

    # pacman-key --lsign-key <fingerprint>
      -> Locally signing key <fingerprint>...
    ==> Updating trust database...
    gpg: next trustdb check due at 2018-06-25


Finally add the repository to ``/etc/pacman.conf``:

::

    [myrepo]
    Server = https://example.com/myrepo
