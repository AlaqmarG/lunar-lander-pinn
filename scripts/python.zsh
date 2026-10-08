# Choose the local environment first, then a Python from PATH.
if [[ -x .venv/bin/python ]]; then
  python_bin=.venv/bin/python
elif [[ -x .venv/Scripts/python.exe ]]; then
  python_bin=.venv/Scripts/python.exe
else
  python_bin=${PYTHON:-python3}
  if ! command -v "$python_bin" >/dev/null 2>&1; then
    if [[ -n ${PYTHON:-} ]]; then
      print -u2 "Python not found: $PYTHON"
      exit 1
    fi
    python_bin=python
  fi
fi
