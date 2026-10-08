"""Check soft goal gradients and hard initial conditions independently of training."""
import json
import torch
from train_game import FlightPINN, ROOT, NAMES, GOAL_SCALES, terms

torch.manual_seed(0)
sc = json.loads((ROOT/'scenario.json').read_text())
model = FlightPINN(sc).double()
terrain = torch.tensor(sc['terrain'], dtype=torch.float64)
s = torch.linspace(0, 1, 17, dtype=torch.float64)[:, None].requires_grad_()
with torch.no_grad():
    model.net[-1].bias[:6].copy_(torch.tensor([.1, -.2, .3, -.4, .5, -.6]))
states = model(torch.tensor([[0.], [1.]], dtype=torch.float64))[:, :6]
torch.testing.assert_close(states[0], torch.tensor(sc['initial'], dtype=torch.float64), atol=1e-12, rtol=0)
errors = states[1] - torch.tensor(sc['target'], dtype=torch.float64)
assert torch.all(errors.abs() > 0), 'Landing states must be free to change'
losses, physics = terms(model, s, terrain)
expected = (errors / torch.tensor(GOAL_SCALES)).square().mean()
torch.testing.assert_close(losses[NAMES.index('landing_goal')], expected)
model.zero_grad()
losses[NAMES.index('landing_goal')].backward()
assert torch.all(model.net[-1].bias.grad[:6].abs() > 0), 'Every landing component needs a goal gradient'
# Time derivative must include d/dt = (1/T) d/ds.
fresh_s = s.detach().clone().requires_grad_()
fresh_states = model(fresh_s)
dx_dt = torch.autograd.grad(fresh_states[:, :1], fresh_s, torch.ones_like(fresh_s), create_graph=True)[0]/sc['horizon']
_, residuals = terms(model, fresh_s, terrain)
torch.testing.assert_close(residuals[0], (dx_dt-fresh_states[:, 2:3])/40)
assert torch.isfinite(losses).all()
print('Passed: exact initial state, free landing endpoints, six goal gradients, goal MSE and physical time scaling')
