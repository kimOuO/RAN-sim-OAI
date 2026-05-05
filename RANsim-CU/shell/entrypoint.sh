#!/usr/bin/env bash
set -euo pipefail

if [ -d /tmp/ran-sim-protocol ]; then
    pip install --no-deps --quiet /tmp/ran-sim-protocol
fi

exec "$@"
