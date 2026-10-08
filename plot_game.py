"""Plot measured game replay and PINN training; no substitute game simulation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parent
out = root/'results'
history = np.atleast_2d(np.loadtxt(out/'loss.csv', delimiter=',', skiprows=1))
names = (out/'loss.csv').read_text().splitlines()[0].split(',')[1:]
fig, axes = plt.subplots(3, 1, figsize=(10,9), sharex=True, constrained_layout=True)
groups = [names[:6], ['landing_goal'], ['terrain_clearance', 'speed_limit', 'fuel_effort']]
for ax, group, title in zip(axes, groups, ['Physics residuals', 'Landing goal (soft terminal condition)', 'Path constraints and thrust effort']):
    for name in group:
        if name in names:
            ax.semilogy(history[:,0],np.maximum(history[:,names.index(name)+1],1e-18),label=name)
    ax.set(title=title,ylabel='Unweighted MSE')
    ax.legend(ncol=3,fontsize=8)
axes[-1].set_xlabel('Adam step, then cumulative L-BFGS evaluations')
fig.suptitle('Separate PINN losses (zero values plotted at 1e-18)')
fig.savefig(out/'loss.png',dpi=130)
plt.close(fig)
policy = json.loads((out/'trained.json').read_text())
replay = json.loads((out/'trained-game-replay.json').read_text())
sc = policy['scenario']
predicted = np.array(policy['predicted_states'])
actual = replay['history']
terrain = np.array(sc['terrain'])
fig,ax = plt.subplots(figsize=(10,6),constrained_layout=True)
ax.fill_between(terrain[:,0],terrain[:,1],sc['height'],color='#60656b',label='Original terrain')
ax.plot(predicted[:,0],predicted[:,1],'--',label='PINN predicted flight')
ax.plot([p['x'] for p in actual],[p['y'] for p in actual],label='Actual original game engine')
ax.plot(sc['pad'],[sc['pad_height']]*2,color='orange',lw=5,label='Landing pad')
ax.set(xlim=(0,sc['width']),ylim=(sc['height'],0),xlabel='Game x (pixels)',ylabel='Game y (pixels)')
ax.set_title('PINN prediction vs actual game flight — '+('landed' if replay['success'] else 'did not land'))
ax.legend()
fig.savefig(out/'flight.png',dpi=130)
plt.close(fig)
print('Saved loss.png and actual game flight.png')
