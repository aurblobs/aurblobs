FROM aurblobs/arch-multilib

RUN pacman -Sy --noconfirm autoconf automake binutils bison fakeroot file \
	flex gawk gcc gettext grep groff libtool m4 make patch pkg-config \
	sudo texinfo util-linux which git xdelta3

RUN rm /usr/share/libalpm/hooks/package-cleanup.hook

COPY sudoers /etc/sudoers
RUN useradd -m build

ENV USER_ID 1000
ENV JOBS 2

COPY entry.sh /entry.sh

# package build root (contains PKGBUILD instruction file)
VOLUME ["/pkg"]

# repository basedir
VOLUME ["/repository"]

# repository signing key
VOLUME ["/privkey.gpg"]

# where pacman downloads repository databases to
VOLUME ["/var/lib/pacman/sync"]

CMD usermod -u $USER_ID build && su -c /entry.sh build
