# syntax=docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# checkov:skip=CKV_DOCKER_3: s6-overlay requires root init so bundled services can prepare state before each service drops privileges
# checkov:skip=CKV_DOCKER_8: s6-overlay entrypoint must start as root so cont-init can initialize persistent state

ARG PENPOT_VERSION=2.16.0
ARG PENPOT_FRONTEND_DIGEST=sha256:78438805e377d8479fe75a3ddd62a0ce767e86b4355d0e2ce7d04a3e0cd5d3cb
ARG PENPOT_BACKEND_DIGEST=sha256:b7a25563d0cabab87abf62eaf2229ade50af0dd310de899f95e6d2f2af63db77
ARG PENPOT_EXPORTER_DIGEST=sha256:ca8e00c7f138bde0e9269093e37ce63c2089b46d462b7b1c3c7f2433dac19286
ARG PENPOT_MCP_DIGEST=sha256:089734934ca4f5e586a8fdef510246a8e3de7a8c2a0f1f0c7a83132c43f1605d
ARG MAILPIT_VERSION=v1.30.2
ARG MAILPIT_IMAGE_DIGEST=sha256:37a38e48e9338cd7e89dfeb487f37b02ebfcd9cb23111bed2d345e79d37d6dd6

FROM jsonbored/aio-base:s6-3.2.1.0@sha256:07db479a01a95ba28480b4605f5d1cc8bedb574b77cf167ee46e29b9558fee90 AS aio-base

FROM penpotapp/frontend:${PENPOT_VERSION}@${PENPOT_FRONTEND_DIGEST} AS frontend
FROM penpotapp/backend:${PENPOT_VERSION}@${PENPOT_BACKEND_DIGEST} AS backend
FROM penpotapp/mcp:${PENPOT_VERSION}@${PENPOT_MCP_DIGEST} AS mcp
FROM axllent/mailpit:${MAILPIT_VERSION}@${MAILPIT_IMAGE_DIGEST} AS mailpit
FROM penpotapp/exporter:${PENPOT_VERSION}@${PENPOT_EXPORTER_DIGEST}

ARG INTERNAL_POSTGRESQL_MAJOR=16

LABEL org.opencontainers.image.source="https://github.com/JSONbored/penpot-aio" \
      org.opencontainers.image.title="penpot-aio" \
      org.opencontainers.image.description="Penpot packaged as a single-container Unraid AIO image with bundled PostgreSQL, Redis-compatible cache, Mailpit, exporter, and MCP"

# hadolint ignore=DL3002
USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Shared, pinned s6-overlay from the fleet aio-base overlay.
COPY --from=aio-base /aio-overlay/ /

# hadolint ignore=DL3003
RUN aio-harden pre && \
    apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y --no-install-recommends \
      ca-certificates="$(apt-cache madison ca-certificates | awk 'NR==1 {print $3}')" \
      curl="$(apt-cache madison curl | awk 'NR==1 {print $3}')" \
      gettext-base="$(apt-cache madison gettext-base | awk 'NR==1 {print $3}')" \
      nginx="$(apt-cache madison nginx | awk 'NR==1 {print $3}')" \
      openssl="$(apt-cache madison openssl | awk 'NR==1 {print $3}')" \
      "postgresql-${INTERNAL_POSTGRESQL_MAJOR}=$(apt-cache madison postgresql-${INTERNAL_POSTGRESQL_MAJOR} | awk 'NR==1 {print $3}')" \
      "postgresql-client-${INTERNAL_POSTGRESQL_MAJOR}=$(apt-cache madison postgresql-client-${INTERNAL_POSTGRESQL_MAJOR} | awk 'NR==1 {print $3}')" \
      redis-server="$(apt-cache madison redis-server | awk 'NR==1 {print $3}')" \
      redis-tools="$(apt-cache madison redis-tools | awk 'NR==1 {print $3}')" \
      xz-utils="$(apt-cache madison xz-utils | awk 'NR==1 {print $3}')" && \
    useradd --system --home-dir /var/lib/mailpit --create-home --shell /usr/sbin/nologin mailpit && \
    mkdir -p /appdata/config /appdata/assets /appdata/logs /appdata/mailpit /appdata/postgres /appdata/redis /run/penpot-aio /run/postgresql /etc/nginx/overrides/http.d && \
    chown -R penpot:penpot /appdata/assets /appdata/logs && \
    chown -R postgres:postgres /appdata/postgres /run/postgresql && \
    chown -R redis:redis /appdata/redis && \
    chown -R mailpit:mailpit /appdata/mailpit && \
    chmod 700 /appdata/postgres /appdata/redis /appdata/mailpit && \
    rm -rf /tmp/* /var/lib/apt/lists/*

COPY --from=backend /opt/jre /opt/jre
COPY --from=backend /opt/penpot/backend /opt/penpot/backend
COPY --from=frontend /var/www/app /var/www/app
COPY --from=frontend /tmp/nginx.conf.template /tmp/nginx.conf.template
COPY --from=frontend /tmp/resolvers.conf.template /tmp/resolvers.conf.template
COPY --from=frontend /etc/nginx/nginx-security-headers.conf /etc/nginx/nginx-security-headers.conf
COPY --from=frontend /etc/nginx/overrides /etc/nginx/overrides
COPY --from=mcp /opt/node /opt/node-mcp
COPY --from=mcp /opt/penpot/mcp /opt/penpot/mcp
COPY --from=mailpit /mailpit /usr/local/bin/mailpit
COPY rootfs/ /

RUN find /etc/cont-init.d -type f -exec chmod +x {} \; && \
    find /etc/services.d -type f -name run -exec chmod +x {} \; && \
    find /usr/local/bin -type f -exec chmod +x {} \; && \
    chown -R penpot:penpot /opt/penpot /var/www/app

VOLUME ["/appdata"]
EXPOSE 8080 8025 4401 4402

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV JAVA_HOME=/opt/jre
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/penpot/browsers
ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=420000
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8080/readyz >/dev/null || exit 1

ENTRYPOINT ["/init"]
