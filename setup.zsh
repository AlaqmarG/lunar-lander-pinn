#!/usr/bin/env zsh
set -eu
cd "${0:A:h}"
device=${1:-cuda}
if [[ $# -gt 1 || ( "$device" != cuda && "$device" != cpu ) ]]; then
  print -u2 'Usage: zsh setup.zsh [cuda|cpu]'
  exit 2
fi
source scripts/python.zsh
if [[ ! -x .venv/bin/python && ! -x .venv/Scripts/python.exe ]]; then
  "$python_bin" -m venv .venv
fi
source scripts/python.zsh
if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
  "$python_bin" -m ensurepip --upgrade
fi
index=https://download.pytorch.org/whl/cu128
[[ "$device" = cpu ]] && index=https://download.pytorch.org/whl/cpu
torch_version=2.11.0+cu128
[[ "$device" = cpu ]] && torch_version=2.11.0+cpu
"$python_bin" -m pip install "torch==$torch_version" --index-url "$index"
"$python_bin" -m pip install -r requirements.txt
if [[ "$device" = cuda ]]; then
  "$python_bin" -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.cuda.get_device_name(0))'
fi
print "Ready. Train with: zsh train.zsh $device"
