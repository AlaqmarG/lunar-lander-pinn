// Calls the unmodified upstream Lander physics/collision code for validation.
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {Keys, controlAt} from './controls.js';
globalThis.window = {addEventListener() {}};
const {default: Lander} = await import('./third_party/lunar_lander/js/lander.js');
const {default: Map} = await import('./third_party/lunar_lander/js/map.js');

const policyPath = process.argv[2] || fileURLToPath(new URL('./results/trained.json', import.meta.url));
const policy = JSON.parse(fs.readFileSync(policyPath));
const sc = policy.scenario;
let rng = sc.seed;
Math.random = () => ((rng = (Math.imul(rng, 1664525)+1013904223) >>> 0) / 4294967296);
Map.generate(30, sc.width, sc.height*.99, sc.height*.7);
if (JSON.stringify(Map.getMap()) !== JSON.stringify(sc.terrain)) throw Error('Map mismatch');
Lander.init(sc.initial[0], sc.initial[1], sc.width, sc.height, sc.config);
const keys = new Keys();
let history = [], frame = 0;
for (; frame < (sc.horizon+3)*sc.fps; frame++) {
    const [throttle, turn] = controlAt(policy, frame);
    Lander.pressed = keys.next(throttle, turn);
    Lander.updatePosition(1/sc.fps);
    history.push({frame, t:(frame+1)/sc.fps, x:Lander.x, y:Lander.y,
                  vx:Lander.v[0], vy:Lander.v[1], theta:Lander.theta, omega:Lander.omega,
                  keys:{...Lander.pressed}, fuel:Lander.fuel});
    if (Lander.isCrashed() || Lander.isLanded()) break;
}
const result = {policy:policy.label, landed:Lander.isLanded(), crashed:Lander.isCrashed(),
    success:Lander.isLanded() && !Lander.isCrashed(), physics_frames:history.length,
    time_seconds:history.length/sc.fps, contact_x:Lander.x, contact_y:Lander.y,
    speed:Lander.getVelocityModule(), angle_degrees:Lander.theta*180/Math.PI,
    fuel_remaining:Lander.fuel, pad:Map.getLandingRange(),
    reached_speed_clamp:history.some(p=>Math.abs(p.vx)>=sc.config.v_max || Math.abs(p.vy)>=sc.config.v_max),
    history};
const out = String(policyPath).replace(/\.json$/, '-game-replay.json');
fs.writeFileSync(out, JSON.stringify(result));
console.log(JSON.stringify({...result,history:undefined},null,2));
