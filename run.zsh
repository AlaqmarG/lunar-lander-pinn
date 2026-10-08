#!/usr/bin/env zsh
set -eu
cd "${0:A:h}"
source scripts/python.zsh
exec "$python_bin" serve.py "$@"
