#!/usr/bin/env bash
# Userspace PostgreSQL + Redis for machines without Docker or sudo.
# See docs/adr/0006-local-dev-services.md.
set -euo pipefail

BASE="${TRYSTSOL_SERVICES_HOME:-$HOME/.local/share/trystsol}"
PGBIN="$BASE/services/bin"
PGBIN_ALT="$BASE/services/bin"
PGDATA="$BASE/pgdata"
RUN="$BASE/run"
LOGS="$BASE/logs"
REDIS="$BASE/redis/bin/redis-server"
REDIS_CLI="$BASE/redis/bin/redis-cli"
PGPORT="${PGPORT:-5433}"
REDISPORT="${REDISPORT:-6380}"

pg_ctl_bin() {
  if [ -x "$PGBIN/pg_ctl" ]; then echo "$PGBIN/pg_ctl"; else echo pg_ctl; fi
}

start() {
  mkdir -p "$PGDATA" "$RUN" "$LOGS" "$BASE/redis"

  if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Initialising PostgreSQL data directory..."
    "$PGBIN/initdb" -D "$PGDATA" -U postgres --auth=trust --encoding=UTF8 --locale=C
  fi

  if ! "$(pg_ctl_bin)" -D "$PGDATA" status >/dev/null 2>&1; then
    "$(pg_ctl_bin)" -D "$PGDATA" -l "$LOGS/postgres.log" \
      -o "-p $PGPORT -k $RUN -c listen_addresses=127.0.0.1" start
  fi

  if ! "$REDIS_CLI" -p "$REDISPORT" ping >/dev/null 2>&1; then
    "$REDIS" --port "$REDISPORT" --bind 127.0.0.1 --daemonize yes \
      --save '' --appendonly no --logfile "$LOGS/redis.log" --dir "$BASE/redis"
  fi

  echo "PostgreSQL: 127.0.0.1:$PGPORT"
  echo "Redis:      127.0.0.1:$REDISPORT"
}

stop() {
  "$(pg_ctl_bin)" -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
  "$REDIS_CLI" -p "$REDISPORT" shutdown nosave >/dev/null 2>&1 || true
  echo "Stopped."
}

status() {
  "$(pg_ctl_bin)" -D "$PGDATA" status || true
  "$REDIS_CLI" -p "$REDISPORT" ping || true
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
