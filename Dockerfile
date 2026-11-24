# syntax=docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# checkov:skip=CKV_DOCKER_3: s6-overlay requires root init so bundled services can prepare state before each service drops privileges
# checkov:skip=CKV_DOCKER_8: s6-overlay entrypoint must start as root so cont-init can initialize persistent state

ARG PENPOT_VERSION=2.19.4
ARG PENPOT_FRONTEND_DIGEST=sha256:387b403d893f69b24694d9390020b3f56a1d06739210d660ddb55606268f02cf
ARG PENPOT_BACKEND_DIGEST=sha256:9e447471d9db381b0c68233027c8cd167d21ff44d466c92a4266da4a82fda5b0
ARG PENPOT_EXPORTER_DIGEST=sha256:11546ad4945d0b3147b98079d40a7a8c4649b518ab3ec56bd22783f0f3c66c21
ARG PENPOT_MCP_DIGEST=sha256:239d2ed817928abf042c55910708cb19eda330917b2fd0d920c86006a2eb4cb1
ARG MAILPIT_VERSION=v1.34.0
ARG MAILPIT_IMAGE_DIGEST=sha256:23a2ef85bc50853ab3093645d1d64679afd8887e89da5e48a88940c172591a4e

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
# The exporter uses Debian Hardened Images, which omit the traditional
# service accounts assumed by Debian's nginx-common postinst.
RUN aio-harden pre && (getent group adm >/dev/null || groupadd --system adm) && \
    (getent passwd www-data >/dev/null || useradd --system --user-group --no-create-home --home-dir /var/www --shell /usr/sbin/nologin www-data) && \
    apt-get update && \
    install -d /usr/share/postgresql-common/pgdg && \
    curl -fsSLo /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    . /etc/os-release && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y --no-install-recommends \
      ca-certificates="$(apt-cache madison ca-certificates | awk 'NR==1 {print $3}')" \
      curl="$(apt-cache madison curl | awk 'NR==1 {print $3}')" \
      gettext-base="$(apt-cache madison gettext-base | awk 'NR==1 {print $3}')" \
      iproute2="$(apt-cache madison iproute2 | awk 'NR==1 {print $3}')" \
      procps="$(apt-cache madison procps | awk 'NR==1 {print $3}')" \
      python3="$(apt-cache madison python3 | awk 'NR==1 {print $3}')" \
      nginx="$(apt-cache madison nginx | awk 'NR==1 {print $3}')" \
      openssl="$(apt-cache madison openssl | awk 'NR==1 {print $3}')" \
      "postgresql-${INTERNAL_POSTGRESQL_MAJOR}=$(apt-cache madison postgresql-${INTERNAL_POSTGRESQL_MAJOR} | awk 'NR==1 {print $3}')" \
      "postgresql-client-${INTERNAL_POSTGRESQL_MAJOR}=$(apt-cache madison postgresql-client-${INTERNAL_POSTGRESQL_MAJOR} | awk 'NR==1 {print $3}')" \
      redis-server="$(apt-cache madison redis-server | awk 'NR==1 {print $3}')" \
      redis-tools="$(apt-cache madison redis-tools | awk 'NR==1 {print $3}')" \
      xz-utils="$(apt-cache madison xz-utils | awk 'NR==1 {print $3}')" && \
    node_path="$(command -v node)" && \
    if [ "$node_path" != "/usr/local/bin/node" ]; then ln -sf "$node_path" /usr/local/bin/node; fi && \
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
COPY --from=frontend /tmp/*.conf.template /tmp/
COPY --from=frontend /etc/nginx /opt/penpot/frontend-nginx
COPY --from=frontend /entrypoint.sh /opt/penpot/render-nginx.sh
COPY --from=frontend /etc/nginx/overrides /etc/nginx/overrides
COPY --from=mcp /opt/penpot/mcp /opt/penpot/mcp
COPY --from=mailpit /mailpit /usr/local/bin/mailpit
COPY rootfs/ /

# The AIO renders JavaScript using JSON string escaping. Reuse the publisher's
# nginx configuration, including its MCP routes, CSP, HSTS and worker limits.
RUN grep -Fxq '## Air Gapped config' /opt/penpot/render-nginx.sh && \
    grep -Fxq '## Nginx Config' /opt/penpot/render-nginx.sh && \
    sed -i '/^## Air Gapped config$/,/^## Nginx Config$/d' /opt/penpot/render-nginx.sh && \
    cp /opt/penpot/frontend-nginx/mime.types /etc/nginx/ && \
    if [ -f /opt/penpot/frontend-nginx/csp-script-hashes.txt ]; then cp /opt/penpot/frontend-nginx/csp-script-hashes.txt /etc/nginx/; fi && \
    find /etc/cont-init.d -type f -exec chmod +x {} \; && \
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
