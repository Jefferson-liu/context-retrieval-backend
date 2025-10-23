#!/bin/bash
set -euo pipefail

CACHE_DIR="${HF_HOME:-/app/.cache/huggingface}"

mkdir -p "${CACHE_DIR}"
chown -R appuser:appuser "${CACHE_DIR}"

exec gosu appuser "$@"
