# 中文分词实验镜像：PostgreSQL 16 + SCWS + zhparser
# 目的：验证 docs/05 §3.4 决策 4 的 "PG tsvector + 中文分词" 在本机与 Docker
# 部署形态下是否真的装得上。这只是实验镜像，不进入部署链路。
FROM postgres:16

ARG SCWS_REF=master
ARG ZHPARSER_REF=master

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential ca-certificates curl postgresql-server-dev-16; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    cd /tmp; \
    curl -fsSL -o scws.tar.gz "https://codeload.github.com/hightman/scws/tar.gz/refs/heads/${SCWS_REF}"; \
    tar xzf scws.tar.gz; \
    cd scws-*; \
    ./configure --prefix=/usr/local; \
    make -j"$(nproc)"; \
    make install; \
    cd /tmp; \
    curl -fsSL -o zhparser.tar.gz "https://codeload.github.com/amutu/zhparser/tar.gz/refs/heads/${ZHPARSER_REF}"; \
    tar xzf zhparser.tar.gz; \
    cd zhparser-*; \
    SCWS_HOME=/usr/local make; \
    SCWS_HOME=/usr/local make install; \
    cd /tmp; \
    rm -rf /tmp/scws* /tmp/zhparser*
