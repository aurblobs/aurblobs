FROM pritunl/archlinux:latest

RUN pacman -Sy --noconfirm base-devel git perl gnupg xdelta3

COPY sudoers /etc/sudoers
RUN useradd -m build

ENV USER_ID 1000

COPY entry.sh /entry.sh

VOLUME ["/pkgroot"]
VOLUME ["/repository"]
VOLUME ["/privkey.gpg"]

CMD ["su", "-c", "/entry.sh", "build"]
