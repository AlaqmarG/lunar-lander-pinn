#!/usr/bin/env zsh
set -eu
cd "${0:A:h}"
device=${1:-cuda}
if [[ $# -gt 1 || ( "$device" != cuda && "$device" != cpu ) ]]; then
  print -u2 'Usage: zsh train.zsh [cuda|cpu]'
  exit 2
fi
source scripts/python.zsh
"$python_bin" test_loss.py
node test_controls.js
"$python_bin" train_game.py --device "$device"
node replay_game.js
node -e 'const r=require("./results/trained-game-replay.json"); if(!r.success) { console.error("The game did not land. Inspect the saved replay."); process.exit(1); }'
"$python_bin" plot_game.py
node verify_adapter.js
print 'Done. Watch the flight with: zsh run.zsh'
