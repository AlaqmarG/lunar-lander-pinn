"""Learn a trajectory and controls for Lunar Lander with an ODE PINN."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
NAMES = ["x_motion", "y_motion", "x_acceleration", "y_acceleration",
         "angle_motion", "angular_acceleration", "landing_goal", "terrain_clearance", "speed_limit", "fuel_effort"]
GOAL_SCALES = [40, 40, 20, 20, 0.3, 1]


class FlightPINN(nn.Module):
    def __init__(self, scenario):
        super().__init__()
        self.scenario = scenario
        self.net = nn.Sequential(nn.Linear(1, 32), nn.Tanh(), nn.Linear(32, 32),
                                 nn.Tanh(), nn.Linear(32, 32), nn.Tanh(), nn.Linear(32, 8))
        for layer in self.net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight)
                nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.net[-1].weight)

    def forward(self, s):
        raw = self.net(s)
        sc = self.scenario
        T = sc["horizon"]
        initial, target = sc["initial"], sc["target"]
        h = 10*s**3 - 15*s**4 + 6*s**5
        dh = 30*s**2 - 60*s**3 + 30*s**4
        k = -4*s**3 + 7*s**4 - 3*s**5
        dk = -12*s**2 + 28*s**3 - 15*s**4
        # Reference curve initializes a useful flight, but does not fix landing.
        # Corrections vanish only at the known initial state, not at s=1.
        x = initial[0] + (target[0]-initial[0])*h + 200*s*raw[:, 0:1]
        y = initial[1] + (target[1]-initial[1])*h + T*target[3]*k + 200*s*raw[:, 1:2]
        vx = (target[0]-initial[0])*dh/T + 40*s*raw[:, 2:3]
        vy = (target[1]-initial[1])*dh/T + target[3]*dk + 40*s*raw[:, 3:4]
        theta = 0.5*s*raw[:, 4:5]
        omega = 0.5*s*raw[:, 5:6]
        throttle = torch.sigmoid(raw[:, 6:7])
        rotation = torch.tanh(raw[:, 7:8])
        return torch.cat([x, y, vx, vy, theta, omega, throttle, rotation], dim=1)


def terms(model, s, terrain):
    states = model(s)
    x, y, vx, vy, theta, omega, thrust, rotation = [states[:, i:i+1] for i in range(8)]
    T = model.scenario["horizon"]

    def d(i):
        return torch.autograd.grad(states[:, i:i+1], s, torch.ones_like(s),
                                   create_graph=True)[0] / T

    g = model.scenario["config"]["gravity"]
    a = model.scenario["config"]["thrust_acceleration"]
    r = model.scenario["config"]["rotate_acceleration"]
    physics = [(d(0)-vx)/40, (d(1)-vy)/40,
               (d(2)-a*thrust*torch.sin(theta))/20,
               (d(3)-g+a*thrust*torch.cos(theta))/20,
               (d(4)-omega)/0.3, (d(5)-r*rotation+0.75*omega)]
    # Sampled footprint clearance: highest sampled ground under center +/- radius.
    terrain_x, terrain_y = terrain[:, 0], terrain[:, 1]
    samples = x + torch.linspace(-15, 15, 7, device=s.device, dtype=s.dtype)[None, :]
    idx = torch.searchsorted(terrain_x.contiguous(), samples.contiguous()).clamp(1, len(terrain_x)-1)
    left_x, right_x = terrain_x[idx-1], terrain_x[idx]
    ground = terrain_y[idx-1] + (samples-left_x)/(right_x-left_x)*(terrain_y[idx]-terrain_y[idx-1])
    clearance = torch.relu((y+15-ground.min(dim=1, keepdim=True).values)/100)
    bounds = (torch.relu(15-x) + torch.relu(x-model.scenario["width"]+15)
              + torch.relu(15-y)) / 100
    speed = torch.relu(torch.abs(states[:, 2:4])-55) / 40
    terminal = model(torch.ones_like(s[:1]))[:, :6]
    target = terminal.new_tensor(model.scenario["target"])[None, :]
    scales = terminal.new_tensor(GOAL_SCALES)[None, :]
    landing_goal = ((terminal-target)/scales).square().mean()
    loss = torch.stack([*(v.square().mean() for v in physics),
                        landing_goal,
                        (clearance.square()+bounds.square()).mean(),
                        speed.square().mean(), thrust.square().mean()])
    return loss, physics


def export_policy(model, path, label):
    T = model.scenario["horizon"]
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    # Samples at every original physics frame; no state is injected into the game.
    times = np.arange(round(T*60)+1)/60
    with torch.no_grad():
        values = model(torch.tensor(times[:, None]/T, device=device, dtype=dtype)).cpu().numpy()
    data = {"label": label, "scenario": model.scenario, "times": times.tolist(),
            "controls": values[:, 6:8].tolist(), "predicted_states": values[:, :6].tolist()}
    path.write_text(json.dumps(data, separators=(",", ":")))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument("--adam", type=int, default=4000)
    p.add_argument("--lbfgs", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--physics-weight", type=float, default=100)
    p.add_argument("--goal-weight", type=float, default=1000)
    p.add_argument("--out", type=Path, default=ROOT/"results")
    args = p.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        p.error("CUDA unavailable. Use a CUDA PyTorch build or --device cpu.")
    if args.adam < 0 or args.lbfgs < 0 or args.adam+args.lbfgs == 0:
        p.error("Use nonnegative counts with at least one optimizer enabled.")
    if not np.isfinite([args.physics_weight, args.goal_weight]).all() or min(args.physics_weight, args.goal_weight) <= 0:
        p.error("Physics and goal weights must be finite and positive.")
    sc = json.loads((ROOT/"scenario.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    device, dtype = torch.device(args.device), torch.float64
    model = FlightPINN(sc).to(device=device, dtype=dtype)
    s = torch.linspace(0, 1, 257, device=device, dtype=dtype)[:, None].requires_grad_()
    terrain = torch.tensor(sc["terrain"], device=device, dtype=dtype)
    weights = torch.tensor([args.physics_weight]*6 + [args.goal_weight, 100, 100, 0.00001], device=device, dtype=dtype)
    export_policy(model, args.out/"untrained.json", "Untrained PINN")
    history = []
    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    print(f"Training flight PINN on {device}", flush=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    for i in range(args.adam):
        optimizer.zero_grad(set_to_none=True)
        s.grad = None
        values, _ = terms(model, s, terrain)
        total = torch.dot(values, weights)
        total.backward()
        optimizer.step()
        if i % 500 == 0 or i == args.adam-1:
            history.append([i, *values.detach().cpu().numpy()])
            print(f"Adam {i}: {total.item():.8g}", flush=True)
    export_policy(model, args.out/"adam.json", "PINN after Adam")
    calls = 0
    if args.lbfgs:
        optimizer = torch.optim.LBFGS(model.parameters(), max_iter=args.lbfgs,
                                      tolerance_grad=1e-10, tolerance_change=1e-14,
                                      line_search_fn="strong_wolfe")

        def closure():
            nonlocal calls
            optimizer.zero_grad(set_to_none=True)
            s.grad = None
            values, _ = terms(model, s, terrain)
            total = torch.dot(values, weights)
            total.backward()
            calls += 1
            if calls % 250 == 0:
                history.append([args.adam+calls, *values.detach().cpu().numpy()])
                print(f"L-BFGS closure {calls}: {total.item():.8g}", flush=True)
            return total

        optimizer.step(closure)
    if args.device == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter()-start
    values, _ = terms(model, s, terrain)
    history.append([args.adam+calls, *values.detach().cpu().numpy()])
    dense = torch.linspace(.00025, .99975, 2000, device=device, dtype=dtype)[:, None].requires_grad_()
    _, residuals = terms(model, dense, terrain)
    with torch.no_grad():
        endpoints = model(s.new_tensor([[0.0], [1.0]]))[:, :6]
        endpoint_errors = endpoints - endpoints.new_tensor([sc["initial"], sc["target"]])
    metrics = {
        "formulation": "strong-form ODE PINN; hard initial state; soft terminal landing goal",
        "loss_groups": {"physics": NAMES[:6], "goal": ["landing_goal"],
                        "constraints": ["terrain_clearance", "speed_limit"], "objective": ["fuel_effort"]},
        "goal_normalization_scales": dict(zip(["x", "y", "vx", "vy", "theta", "omega"], GOAL_SCALES)),
        "predicted_initial_error": endpoint_errors[0].cpu().tolist(),
        "predicted_terminal_state": endpoints[1].cpu().tolist(),
        "predicted_terminal_error": endpoint_errors[1].cpu().tolist(),
        "device": str(next(model.parameters()).device), "gpu": torch.cuda.get_device_name(0) if args.device == "cuda" else None,
        "torch": torch.__version__, "dtype": str(dtype), "seed": args.seed,
        "training_seconds": elapsed, "adam_steps": args.adam, "lbfgs_closure_evaluations": calls,
        "cuda_peak_allocated_mb": torch.cuda.max_memory_allocated()/2**20 if args.device == "cuda" else None,
        "loss_weights": dict(zip(NAMES, weights.detach().cpu().tolist())),
        "final_unweighted_losses": dict(zip(NAMES, values.detach().cpu().tolist())),
        "dense_normalized_residual_rmse": {name: float(v.detach().square().mean().sqrt().cpu()) for name,v in zip(NAMES[:6],residuals)},
        "game_validation": "pending; run replay_game.js and browser validation",
    }
    export_policy(model, args.out/"trained.json", "Trained PINN")
    torch.save({"state_dict": model.state_dict(), "scenario": sc, "metrics": metrics}, args.out/"flight_pinn.pt")
    (args.out/"training.json").write_text(json.dumps(metrics, indent=2)+"\n")
    np.savetxt(args.out/"loss.csv", history, delimiter=",", header="step_or_closure,"+",".join(NAMES), comments="")
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
