FROM library/alpine:3
COPY hello.sh /
COPY goodbye.sh /
ENV DESCRIPTION=Flattenator\ Test\ Container
WORKDIR /tmp
USER 405:100
CMD ["/hello.sh"]

