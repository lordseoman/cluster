FROM python:2.7

RUN apt-get update \
  && apt-get install --yes --no-install-recommends vim jq screen mailutils

RUN mkdir /usr/src/work
COPY requirements.txt /usr/src/work/requirements.txt
RUN pip install -r /usr/src/work/requirements.txt

RUN mkdir /opt/overseer
COPY code/ /opt/overseer/
ADD .screenrc /root/
ADD .vimrc /root/

ADD entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 3000 13001 13002

CMD ["start"]
