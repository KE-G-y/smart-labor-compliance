#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"
START_LOCAL_SERVICES="${START_LOCAL_SERVICES:-auto}"
BACKEND_RELOAD="${BACKEND_RELOAD:-1}"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
STARTED_BACKEND=0
STARTED_FRONTEND=0

log() {
  printf '[smart-labor] %s\n' "$*"
}

fail() {
  printf '[smart-labor] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup_on_exit() {
  local status="$?"
  if [[ "$status" -ne 0 && ( "$STARTED_BACKEND" == "1" || "$STARTED_FRONTEND" == "1" ) ]]; then
    log "启动未完成，回滚本次已启动进程..."
    "$ROOT_DIR/scripts/stop_project.sh" || true
  fi
  exit "$status"
}

trap cleanup_on_exit EXIT

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

pid_is_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 0
  tr -d '[:space:]' < "$pid_file"
}

install_enabled() {
  case "$INSTALL_DEPS" in
    0|false|FALSE|no|NO) return 1 ;;
    *) return 0 ;;
  esac
}

local_services_enabled() {
  case "$START_LOCAL_SERVICES" in
    0|false|FALSE|no|NO) return 1 ;;
    *) return 0 ;;
  esac
}

reload_enabled() {
  case "$BACKEND_RELOAD" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

detect_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    command_exists "$PYTHON_BIN" || fail "PYTHON_BIN 不可执行：$PYTHON_BIN"
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi

  local candidate
  for candidate in python python3; do
    if command_exists "$candidate" && "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

port_pids() {
  local port="$1"
  command_exists lsof || return 0
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u
}

write_port_pid_file() {
  local name="$1"
  local port="$2"
  local pid_file="$3"
  local pids

  pids="$(port_pids "$port" || true)"
  if [[ -z "$pids" ]]; then
    fail "无法记录 ${name} 的监听 PID，端口 $port 未发现监听进程"
  fi

  printf '%s\n' "$pids" > "$pid_file"
}

ensure_port_free() {
  local name="$1"
  local port="$2"
  local pids
  pids="$(port_pids "$port" || true)"
  [[ -z "$pids" ]] && return 0

  fail "$name 端口 $port 已被占用，PID：$(printf '%s\n' "$pids" | tr '\n' ' ')"
}

ensure_backend_env() {
  if [[ -f "$BACKEND_DIR/.env" ]]; then
    return 0
  fi

  if [[ -f "$BACKEND_DIR/.env.example" ]]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    log "已生成本地后端配置：backend/.env"
    return 0
  fi

  fail "缺少 backend/.env，且未找到 backend/.env.example"
}

ensure_root_env() {
  if [[ -f "$ROOT_DIR/.env" || ! -f "$ROOT_DIR/.env.example" ]]; then
    return 0
  fi

  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  log "已生成 Docker Compose 配置：.env"
}

compose_env_value() {
  local key="$1"
  local default_value="$2"
  local value=""

  if [[ -f "$ROOT_DIR/.env" ]]; then
    value="$(awk -F= -v key="$key" '$1 == key {print substr($0, length(key) + 2); exit}' "$ROOT_DIR/.env")"
  fi

  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

port_owned_by_compose() {
  local port="$1"
  local pids
  local pid
  local command_line

  pids="$(port_pids "$port" || true)"
  [[ -n "$pids" ]] || return 1

  for pid in $pids; do
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" != *"com.docker"* && "$command_line" != *"docker"* ]]; then
      return 1
    fi
  done

  return 0
}

ensure_compose_port_free() {
  local name="$1"
  local port="$2"
  local pids

  pids="$(port_pids "$port" || true)"
  [[ -z "$pids" ]] && return 0
  port_owned_by_compose "$port" && return 0

  fail "$name 端口 $port 已被占用，PID：$(printf '%s\n' "$pids" | tr '\n' ' ')"
}

ensure_compose_ports_free() {
  local mysql_port
  local minio_api_port
  local minio_console_port
  local milvus_port
  local milvus_webui_port

  mysql_port="$(compose_env_value MYSQL_HOST_PORT 3306)"
  minio_api_port="$(compose_env_value MINIO_API_HOST_PORT 9000)"
  minio_console_port="$(compose_env_value MINIO_CONSOLE_HOST_PORT 9001)"
  milvus_port="$(compose_env_value MILVUS_HOST_PORT 19530)"
  milvus_webui_port="$(compose_env_value MILVUS_WEBUI_HOST_PORT 9091)"

  ensure_compose_port_free "Docker MySQL" "$mysql_port"
  ensure_compose_port_free "Docker MinIO API" "$minio_api_port"
  ensure_compose_port_free "Docker MinIO Console" "$minio_console_port"
  ensure_compose_port_free "Docker Milvus" "$milvus_port"
  ensure_compose_port_free "Docker Milvus WebUI" "$milvus_webui_port"
}

compose_service_network_attached() {
  local service="$1"
  local container_id
  local networks

  container_id="$(docker compose ps -q "$service" 2>/dev/null || true)"
  [[ -n "$container_id" ]] || return 1

  networks="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' "$container_id" 2>/dev/null || true)"
  [[ -n "$networks" ]]
}

compose_services_network_attached() {
  compose_service_network_attached mysql \
    && compose_service_network_attached minio \
    && compose_service_network_attached etcd \
    && compose_service_network_attached milvus
}

wait_for_compose_service() {
  local service="$1"
  local name="$2"
  local seconds="${3:-180}"
  local container_id
  local status
  local i

  for ((i = 1; i <= seconds; i += 1)); do
    container_id="$(docker compose ps -q "$service" 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      if [[ "$status" == "healthy" || "$status" == "running" ]]; then
        log "${name} 已就绪"
        return 0
      fi
    fi

    sleep 1
  done

  docker compose ps "$service" >&2 || true
  fail "${name} 在 ${seconds}s 内未就绪"
}

ensure_local_services() {
  local mysql_running
  local minio_running
  local milvus_running

  local_services_enabled || return 0
  command_exists docker || {
    log "未检测到 docker，跳过 MySQL/MinIO/Milvus 自动启动；请确认本机服务已就绪"
    return 0
  }

  ensure_root_env

  mysql_running=0
  minio_running=0
  milvus_running=0
  if command_exists docker; then
    [[ -n "$(docker compose ps --status running -q mysql 2>/dev/null)" ]] && mysql_running=1 || true
    [[ -n "$(docker compose ps --status running -q minio 2>/dev/null)" ]] && minio_running=1 || true
    [[ -n "$(docker compose ps --status running -q milvus 2>/dev/null)" ]] && milvus_running=1 || true
  fi

  if [[ "$mysql_running" == "1" && "$minio_running" == "1" && "$milvus_running" == "1" ]]; then
    if compose_services_network_attached; then
      log "本地 MySQL/MinIO/Milvus 依赖服务已运行"
      return 0
    fi

    log "检测到 Docker 依赖容器网络状态异常，将重新创建依赖容器"
  else
    ensure_compose_ports_free
  fi

  log "启动本地依赖服务：mysql、etcd、minio、milvus..."
  docker compose up -d --force-recreate mysql etcd minio milvus
  wait_for_compose_service "mysql" "MySQL" 120
  wait_for_compose_service "minio" "MinIO" 120
  wait_for_compose_service "milvus" "Milvus" 240
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local pid_file="$3"
  local log_file="$4"
  local seconds="${5:-60}"
  local pid
  local i

  command_exists curl || fail "缺少 curl，无法检查 $name 是否启动完成"

  for ((i = 1; i <= seconds; i += 1)); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      log "${name} 已就绪：$url"
      return 0
    fi

    pid="$(read_pid_file "$pid_file" || true)"
    if [[ -n "$pid" ]] && ! pid_is_alive "$pid"; then
      tail -n 40 "$log_file" >&2 || true
      fail "${name} 启动失败，完整日志见 $log_file"
    fi

    sleep 1
  done

  tail -n 40 "$log_file" >&2 || true
  fail "${name} 在 ${seconds}s 内未就绪，完整日志见 $log_file"
}

ensure_backend_deps() {
  if "$PYTHON_BIN" -c "import fastapi, uvicorn, pymysql, sqlalchemy" >/dev/null 2>&1; then
    :
  else
    install_enabled || fail "后端依赖不完整。请执行：cd backend && $PYTHON_BIN -m pip install -r requirements.txt"

    log "安装/补齐后端依赖..."
    (cd "$BACKEND_DIR" && "$PYTHON_BIN" -m pip install -r requirements.txt)
  fi

  if grep -q '^LOCAL_.*_ENABLED=true' "$BACKEND_DIR/.env" 2>/dev/null; then
    if "$PYTHON_BIN" -c "import torch, transformers, sentence_transformers" >/dev/null 2>&1; then
      return 0
    fi

    if [[ -f "$BACKEND_DIR/requirements-local-models.txt" ]]; then
      log "检测到本地模型已启用，安装/补齐本地模型依赖..."
      (cd "$BACKEND_DIR" && "$PYTHON_BIN" -m pip install -r requirements-local-models.txt)
    else
      log "本地模型已启用，但缺少 requirements-local-models.txt；将由后端在运行时自动回退"
    fi
  fi
}

ensure_frontend_deps() {
  command_exists npm || fail "缺少 npm，请先安装 Node.js"

  if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
    return 0
  fi

  install_enabled || fail "前端依赖不完整。请执行：cd frontend && npm install"

  log "安装前端依赖..."
  (cd "$FRONTEND_DIR" && npm install)
}

start_backend() {
  local pid
  local backend_args
  pid="$(read_pid_file "$BACKEND_PID_FILE" || true)"
  if pid_is_alive "$pid"; then
    log "后端已在运行，PID：$pid"
    wait_for_http "后端 API" "http://127.0.0.1:$BACKEND_PORT/health" "$BACKEND_PID_FILE" "$BACKEND_LOG" 15
    return 0
  fi

  rm -f "$BACKEND_PID_FILE"
  ensure_port_free "后端 API" "$BACKEND_PORT"
  ensure_backend_deps

  log "启动后端 API..."
  printf '\n== %s start backend on %s:%s, reload=%s ==\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$BACKEND_HOST" "$BACKEND_PORT" "$BACKEND_RELOAD" >> "$BACKEND_LOG"
  backend_args=("$PYTHON_BIN" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT")
  if reload_enabled; then
    backend_args+=(--reload --reload-dir app --reload-dir scripts)
  fi
  (
    cd "$BACKEND_DIR"
    PYTHONUNBUFFERED=1 nohup "${backend_args[@]}" >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )
  STARTED_BACKEND=1

  wait_for_http "后端 API" "http://127.0.0.1:$BACKEND_PORT/health" "$BACKEND_PID_FILE" "$BACKEND_LOG" 60
  write_port_pid_file "后端 API" "$BACKEND_PORT" "$BACKEND_PID_FILE"
}

start_frontend() {
  local pid
  local api_target
  pid="$(read_pid_file "$FRONTEND_PID_FILE" || true)"
  if pid_is_alive "$pid"; then
    log "前端已在运行，PID：$pid"
    wait_for_http "前端页面" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_PID_FILE" "$FRONTEND_LOG" 15
    return 0
  fi

  rm -f "$FRONTEND_PID_FILE"
  ensure_port_free "前端页面" "$FRONTEND_PORT"
  ensure_frontend_deps

  api_target="${VITE_API_PROXY_TARGET:-http://127.0.0.1:$BACKEND_PORT}"
  log "启动前端页面..."
  printf '\n== %s start frontend on %s:%s, proxy %s ==\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$FRONTEND_HOST" "$FRONTEND_PORT" "$api_target" >> "$FRONTEND_LOG"
  (
    cd "$FRONTEND_DIR"
    VITE_API_PROXY_TARGET="$api_target" nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" >> "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )
  STARTED_FRONTEND=1

  wait_for_http "前端页面" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_PID_FILE" "$FRONTEND_LOG" 60
  write_port_pid_file "前端页面" "$FRONTEND_PORT" "$FRONTEND_PID_FILE"
}

PYTHON_BIN="$(detect_python || true)"
[[ -n "$PYTHON_BIN" ]] || fail "未找到 Python 3.10+。可通过 PYTHON_BIN=python3 指定解释器"

mkdir -p "$RUN_DIR" "$LOG_DIR"

log "项目根目录：$ROOT_DIR"
log "Python 解释器：$PYTHON_BIN"

ensure_backend_env
ensure_local_services
start_backend
start_frontend

log "启动完成"
printf '前端页面：%s\n' "http://localhost:$FRONTEND_PORT"
printf '后端接口：%s\n' "http://127.0.0.1:$BACKEND_PORT"
printf 'API 文档：%s\n' "http://127.0.0.1:$BACKEND_PORT/docs"
printf '日志目录：%s\n' "$LOG_DIR"
