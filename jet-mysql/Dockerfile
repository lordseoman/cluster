FROM debian:jessie-slim

MAINTAINER Simon Hookway <simon@obsidian.com.au>

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG TIMEZONE
ARG MODULE
ARG VERSION
ARG CLIENT
ARG MACHINE

ENV HTTP_PROXY ${HTTP_PROXY:-}
ENV HTTPS_PROXY ${HTTPS_PROXY:-}
ENV NO_PROXY ''
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
  && apt-get install --yes apt-utils vim less htop wget unzip curl locales net-tools screen tcpdump strace patch mailutils \
  && echo "en_US.UTF-8 UTF-8" > /etc/locale.gen \
  && /usr/sbin/locale-gen en_US.UTF-8 \
  && dpkg-reconfigure -f noninteractive locales \
  && /usr/sbin/update-locale LANG=en_US.UTF-8

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV LC_ALL en_US.UTF-8

# Fix timezone
RUN rm /etc/localtime \
  && ln -sv /usr/share/zoneinfo/$TIMEZONE /etc/localtime \
  && dpkg-reconfigure -f noninteractive tzdata

# Add the proxy to /etc/bash.bashrc
RUN echo "\n\nexport http_proxy=$HTTP_PROXY\nexport https_proxy=$HTTPS_PROXY" >> /etc/bash.bashrc

# Install Supervisor and stuff
RUN apt-get install --yes --no-install-recommends apt-transport-https ca-certificates gnupg2 software-properties-common supervisor cron logrotate \
  && mkdir -p /var/log/supervisor \
  && mkdir -p /etc/supervisor/conf.d

# Install MySQLdb
RUN apt-get install --yes mysql-server-5.5 mysql-client-5.5

# Install AWSLOGS Dependencies
RUN apt-get install --yes --no-install-recommends libtool pkg-config build-essential autoconf automake uuid-dev python-dev

RUN apt-get install --yes --no-install-recommends python-pip
RUN mkdir /usr/src/work
COPY requirements.txt /usr/src/work/requirements.txt
RUN pip install -r /usr/src/work/requirements.txt

# Copy config files and stuff before setting up.
COPY mysql-conf/my.cnf /etc/mysql/
COPY mysql-conf/debian.cnf /etc/mysql/
COPY mysql-conf/conf.d/ /etc/mysql/conf.d/
COPY mysql-conf/mysql-$MACHINE.cnf /etc/mysql/
COPY mysql-conf/mysql-$CLIENT.cnf /etc/mysql/
RUN echo "\n!include /etc/mysql/mysql-${MACHINE}.cnf\n!include /etc/mysql/mysql-${CLIENT}.cnf" >> /etc/mysql/my.cnf
COPY conf/supervisord.conf /etc/supervisor/
COPY conf/supervisor.conf.d/ /etc/supervisor/conf.d/
COPY skel/root/ /root/
COPY conf/defaults /root/

RUN mkdir -p /opt/Database && chown mysql:mysql /opt/Database

RUN /root/bin/on-build.sh
RUN /root/bin/apply_patches.sh
RUN rm -rf /root/bin/on-build.sh /root/bin/apply_patches.sh /root/patches

ENV HOME /root

ADD entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

STOPSIGNAL SIGTERM

VOLUME ["/opt/Database"]
EXPOSE 3306 9001

CMD ["start"]

