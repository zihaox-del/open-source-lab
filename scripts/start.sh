#!/usr/bin/env sh
# Local-only launcher. No global installation or security-setting changes.
set -eu
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
else
  PYTHON=python3
fi
"$PYTHON" -m websheet.preflight
printf '\n打开 http://127.0.0.1:8765 。保持此窗口开启；Ctrl+C 停止服务。\n'
exec "$PYTHON" -m websheet
