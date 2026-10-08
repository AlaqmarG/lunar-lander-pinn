import fs from 'node:fs';
import Map from './third_party/lunar_lander/js/map.js';
import Config from './third_party/lunar_lander/js/config.js';

const seed = 123;
let state = seed;
Math.random = () => ((state = (Math.imul(state, 1664525) + 1013904223) >>> 0) / 4294967296);
const width = 800, height = 600;
Map.generate(30, width, height * .99, height * .7);
const range = Map.getLandingRange();
const scenario = {
    seed, width, height, fps: 60, level: 'EASY', initial: [200, 200, 0, 0, 0, 0],
    terrain: Map.getMap(), pad: range, pad_height: Map.landing_zone_height,
    target: [(range[0] + range[1]) / 2, Map.landing_zone_height - 15, 0, 8, 0, 0],
    horizon: 12, config: Config.EASY, collider_radius: 15,
};
fs.writeFileSync(new URL('./scenario.json', import.meta.url), JSON.stringify(scenario, null, 2) + '\n');
console.log(JSON.stringify(scenario));
