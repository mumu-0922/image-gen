#!/usr/bin/env bash
set -euo pipefail

append_v1=1
request_timeout="${IMAGE_GEN_REQUEST_TIMEOUT:-600}"
use_uv=0
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-append-v1|--noappendv1)
      append_v1=0
      shift
      ;;
    --use-uv)
      use_uv=1
      shift
      ;;
    --request-timeout)
      [[ $# -ge 2 ]] || { echo "error: --request-timeout requires a value" >&2; exit 1; }
      request_timeout="$2"
      shift 2
      ;;
    --)
      shift
      args+=("$@")
      break
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

fail() { echo "error: $*" >&2; exit 1; }

[[ ${#args[@]} -gt 0 ]] || fail "Missing imagegen CLI arguments. Example: generate-batch --input ./references/relay-test.jsonl --out-dir ./output/imagegen-relay-test --dry-run"

codex_home="${CODEX_HOME:-$HOME/.codex}"
config_path="$codex_home/config.toml"
auth_path="$codex_home/auth.json"
engine_path="${IMAGE_GEN_ENGINE:-$codex_home/skills/.system/imagegen/scripts/image_gen.py}"
timeout_wrapper_path="$codex_home/skills/image-gen/scripts/imagegen_with_timeout.py"

[[ -f "$config_path" ]] || fail "Codex config.toml not found: $config_path"
[[ -f "$auth_path" ]] || fail "Codex auth.json not found: $auth_path"
[[ -f "$engine_path" ]] || fail "System imagegen CLI not found: $engine_path"
[[ -f "$timeout_wrapper_path" ]] || fail "Timeout wrapper not found: $timeout_wrapper_path"

base_url="$({ python3 - "$config_path" "$append_v1" <<'PY'
from __future__ import annotations
import re, sys
path, append = sys.argv[1], sys.argv[2] == "1"
text = open(path, "r", encoding="utf-8").read()
match = re.search(r'(?m)^\s*base_url\s*=\s*"([^"]+)"', text)
if not match:
    print("error: No base_url found in Codex config.toml", file=sys.stderr)
    raise SystemExit(1)
base = match.group(1).strip()
if append and not base.rstrip('/').endswith('/v1'):
    base = base.rstrip('/') + '/v1'
print(base)
PY
} )" || exit $?

api_key="$({ python3 - "$auth_path" <<'PY'
from __future__ import annotations
import json, sys
try:
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
except Exception as exc:
    print(f"error: could not read auth.json: {exc}", file=sys.stderr)
    raise SystemExit(1)
key = data.get("OPENAI_API_KEY") or data.get("api_key")
if not key:
    print("error: No OPENAI_API_KEY found in Codex auth.json", file=sys.stderr)
    raise SystemExit(1)
print(key)
PY
} )" || exit $?

export OPENAI_BASE_URL="$base_url"
export OPENAI_API_KEY="$api_key"
export IMAGE_GEN_ENGINE="$engine_path"
export IMAGE_GEN_REQUEST_TIMEOUT="$request_timeout"

printf 'Using OPENAI_BASE_URL: %s\n' "$OPENAI_BASE_URL"
printf 'Using OPENAI_API_KEY: <set>\n'
printf 'Using IMAGE_GEN_REQUEST_TIMEOUT: %s\n' "$IMAGE_GEN_REQUEST_TIMEOUT"

is_dry_run=0
for arg in "${args[@]}"; do
  [[ "$arg" == "--dry-run" ]] && is_dry_run=1 && break
done

uv_bin="${UV:-}"
if [[ -z "$uv_bin" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv_bin="$(command -v uv)"
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    uv_bin="$HOME/.local/bin/uv"
  elif [[ -x "$HOME/.cargo/bin/uv" ]]; then
    uv_bin="$HOME/.cargo/bin/uv"
  fi
fi

if [[ $is_dry_run -eq 0 ]] && [[ $use_uv -eq 1 || -n "$uv_bin" ]]; then
  [[ -n "$uv_bin" && -x "$uv_bin" ]] || fail "uv not found/executable: ${uv_bin:-<empty>}"
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"
  exec "$uv_bin" run --with openai --with pillow python3 "$timeout_wrapper_path" "${args[@]}"
fi

python_bin="${IMAGE_GEN_PYTHON:-python3}"
exec "$python_bin" "$timeout_wrapper_path" "${args[@]}"
