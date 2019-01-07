FROM redis:alpine

RUN apk add --no-cache curl

ADD entrypoint.sh /entrypoint-discover.sh
RUN chmod +x /entrypoint-discover.sh
ENTRYPOINT ["/entrypoint-discover.sh"]
