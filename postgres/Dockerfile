FROM postgres:18.7-alpine3.24@sha256:0115267ab5a509022df9319c77be365cef335adb71556c75f60f5360ee247e71 AS build
RUN apk add --no-cache build-base git
RUN git clone --depth 1 --branch v0.8.7 https://github.com/pgvector/pgvector.git /src \
    && cd /src \
    && test "$(git rev-parse HEAD)" = f37c13f68b57d2c3472b2214fbcff699d6d34876 \
    && test "$(pg_config --version)" = 'PostgreSQL 18.7' \
    && make PG_CONFIG="$(command -v pg_config)" OPTFLAGS="" with_llvm=no \
    && make PG_CONFIG="$(command -v pg_config)" OPTFLAGS="" with_llvm=no DESTDIR=/stage install

FROM postgres:18.7-alpine3.24@sha256:0115267ab5a509022df9319c77be365cef335adb71556c75f60f5360ee247e71
COPY --from=build /stage/ /
