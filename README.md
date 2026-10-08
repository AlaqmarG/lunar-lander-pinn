# Lunar Lander PINN

I started with the idea of a neural network learning to drive in Trackmania.
For a quick PINN experiment, Lunar Lander was easier to work with because I could
read its gravity, thrust and turning rules directly in the game code.

This project uses a small PyTorch MLP to plan one flight. It takes normalized
time as input and predicts eight values: position `x, y`, velocity `vx, vy`,
angle, angular velocity, throttle and turn. Training uses the motion equations
and a landing target, without recorded gameplay, a genetic algorithm or
reinforcement learning. The trained controls are played back in the original
JavaScript game, which handles movement, fuel and collisions.

## Watch it

You need Python 3 and a browser to watch the saved flight. From this folder:

```zsh
zsh run.zsh
```

Open <http://127.0.0.1:8137/>. The page lets you switch between trained and
untrained flights, pause, restart, change speed or fly with the arrow keys.
Keep the serving terminal open. If the port is busy, use
`zsh run.zsh --port 8138`.

## Train it

Use Python 3.12 and Node.js. For an NVIDIA GPU with a compatible driver:

```zsh
zsh setup.zsh cuda
zsh train.zsh cuda
```

For CPU training:

```zsh
zsh setup.zsh cpu
zsh train.zsh cpu
```

Setup creates a local `.venv`. The scripts support both `.venv/bin/python` and
Windows' `.venv/Scripts/python.exe`. You can set `PYTHON` to choose the interpreter
used to create the environment.

## How the loss works

The initial state is fixed in the network output. Physics and the landing goal
are separate penalties:

```text
L = 100 L_physics + 1000 L_goal
  + 100 L_clearance + 100 L_speed + 1e-5 L_thrust
```

- **Physics:** squared errors in six motion equations, calculated with PyTorch
  automatic differentiation and scaled before averaging.
- **Goal:** scaled final position, velocity, angle and angular-velocity errors
  against the landing target at 12 seconds.
- **Clearance:** terrain overlap and screen-boundary violations.
- **Speed:** penalizes either velocity component exceeding 55 in magnitude.
- **Thrust:** average squared throttle, a small preference for less thrust.
  It is a proxy for effort, not a measurement of fuel use.

I chose these weights by hand. Training used 4,000 Adam updates followed by
L-BFGS refinement and took about 7.5 minutes on an RTX 3070. The game accepted
the landing at 11.98 seconds. That result covers one fixed map and one seed.
The plan doesn't adapt during flight, and I haven't established the fastest route.

## Files

`train_game.py` holds the model and loss. `replay_game.js` checks the learned
controls in the original engine. `watch.js` connects them to the viewer.
`test_loss.py`, `test_controls.js` and `verify_adapter.js` check the loss and
control adapter. `results/` contains the saved policies, replay and plots.
Training again writes new results there.

The game is cscazorla's JavaScript Lunar Lander. Its files are unchanged,
with the original MIT license in `third_party/lunar_lander/LICENSE`.
