FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
  openjdk-17-jdk-headless \
  binutils \
  && rm -rf /var/lib/apt/lists/*

RUN jlink \
  --add-modules java.base,java.desktop,java.logging,java.xml,java.datatransfer,java.prefs,jdk.unsupported\
  --strip-debug \
  --no-man-pages \
  --no-header-files \
  --compress=2 \
  --output /opt/jre-minimal

FROM debian:12-slim

RUN groupadd -r netlogo && useradd -r -g netlogo -d /NetLogo -s /usr/sbin/nologin netlogo \
  && apt-get update && apt-get install -y --no-install-recommends \
  python3 \
  fontconfig \
  libfreetype6 \
  libharfbuzz0b \
  ca-certificates \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/jre-minimal /opt/jre
ENV JAVA_HOME=/opt/jre
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

COPY --chown=root:root . /NetLogo
WORKDIR /NetLogo

RUN chmod -R a-w /NetLogo \
  && chmod +x /NetLogo/entrypoint.sh

VOLUME /tmp

USER netlogo:netlogo

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
