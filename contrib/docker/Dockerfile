FROM fleaz/arch-multilib

RUN pacman -Sy --noconfirm autoconf automake binutils bison fakeroot file \
	findutils flex gawk gcc-multilib gettext grep groff gzip libtool m4 make \
	pacman patch pkg-config sed sudo texinfo util-linux which git perl gnupg xdelta3

COPY sudoers /etc/sudoers
RUN useradd -m build

ENV USER_ID 1000
ENV JOBS 2

COPY entry.sh /entry.sh

VOLUME ["/pkgroot"]
VOLUME ["/repository"]
VOLUME ["/privkey.gpg"]

CMD usermod -u $USER_ID build && su -c /entry.sh build
