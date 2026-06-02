# syntax=docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# checkov:skip=CKV_DOCKER_3: s6-overlay requires root init so bundled services can prepare state before each service drops privileges
# checkov:skip=CKV_DOCKER_8: s6-overlay entrypoint must start as root so cont-init can initialize persistent state

ARG PENPOT_VERSION=2.15.4
ARG PENPOT_FRONTEND_DIGEST=sha256:a918223cbcac28626fb879506f98d9a4550b75cc84827833f751488b18be1397
ARG PENPOT_BACKEND_DIGEST=sha256:489e15cdcc38861282e4007281539599c5989efdd5392d018bc73b5b3f6c349c
ARG PENPOT_EXPORTER_DIGEST=sha256:f53df624f4f2cb649075070b160a0365d1e2060aad82450ae8402417f97f0508
ARG PENPOT_MCP_DIGEST=sha256:d23111451527c96b6417da2ec565fa190d520a82b9bf95ecf09e9f0cda23439a
ARG MAILPIT_VERSION=v1.30.1
ARG MAILPIT_IMAGE_DIGEST=sha256:3bd7c2f2696deb35a4780d152b404dceec99cb041b942c0877b3b22384714f85

FROM penpotapp/frontend:${PENPOT_VERSION}@${PENPOT_FRONTEND_DIGEST} AS frontend
FROM penpotapp/backend:${PENPOT_VERSION}@${PENPOT_BACKEND_DIGEST} AS backend
FROM penpotapp/mcp:${PENPOT_VERSION}@${PENPOT_MCP_DIGEST} AS mcp
FROM axllent/mailpit:${MAILPIT_VERSION}@${MAILPIT_IMAGE_DIGEST} AS mailpit
FROM penpotapp/exporter:${PENPOT_VERSION}@${PENPOT_EXPORTER_DIGEST}

ARG S6_OVERLAY_VERSION=3.2.1.0
ARG INTERNAL_POSTGRESQL_MAJOR=16
ARG TARGETARCH

LABEL org.opencontainers.image.source="https://github.com/JSONbored/penpot-aio" \
      org.opencontainers.image.title="penpot-aio" \
      org.opencontainers.image.description="Penpot packaged as a single-container Unraid AIO image with bundled PostgreSQL, Redis-compatible cache, Mailpit, exporter, and MCP"

# hadolint ignore=DL3002
USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3003
RUN find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -exec sed -i 's|http://|https://|g' {} + && \
    printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' > /etc/apt/apt.conf.d/80-retries && \
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
    curl -fsSL -o /tmp/s6-overlay-noarch.tar.xz "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" && \
    curl -fsSL -o /tmp/s6-overlay-noarch.tar.xz.sha256 "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz.sha256" && \
    (cd /tmp && sha256sum -c s6-overlay-noarch.tar.xz.sha256) && \
    tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    case "${TARGETARCH}" in \
      amd64) s6_arch="x86_64" ;; \
      arm64) s6_arch="aarch64" ;; \
      *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL -o "/tmp/s6-overlay-${s6_arch}.tar.xz" "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${s6_arch}.tar.xz" && \
    curl -fsSL -o "/tmp/s6-overlay-${s6_arch}.tar.xz.sha256" "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${s6_arch}.tar.xz.sha256" && \
    (cd /tmp && sha256sum -c "s6-overlay-${s6_arch}.tar.xz.sha256") && \
    tar -C / -Jxpf "/tmp/s6-overlay-${s6_arch}.tar.xz" && \
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
