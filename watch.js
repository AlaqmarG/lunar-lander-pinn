import Game from './third_party/lunar_lander/js/game.js';
import Lander from './third_party/lunar_lander/js/lander.js';
import Map from './third_party/lunar_lander/js/map.js';
import {Keys, controlAt} from './controls.js';

const $ = id => document.getElementById(id);
let mode = 'trained', frame = 0, paused = false, quantizer = new Keys();
let policies, scenario;
const history = [];
const originalUpdate = Game.update.bind(Game);

function seedMap() {
    let seed = scenario.seed;
    const previous = Math.random;
    Math.random = () => ((seed = (Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
    Map.generate(30, scenario.width, scenario.height*.99, scenario.height*.7);
    Math.random = previous;
    if (JSON.stringify(Map.getMap()) !== JSON.stringify(scenario.terrain)) throw Error('Scenario terrain mismatch');
}

function reset(nextMode = mode) {
    mode = nextMode; frame = 0; paused = false; quantizer = new Keys(); history.length = 0;
    seedMap();
    Lander.init(scenario.initial[0],scenario.initial[1],scenario.width,scenario.height,scenario.config);
    Lander.pressed = {up:false,left:false,right:false};
    Game.gameover = false;
    $('gameover').style.display = 'none'; $('gameover').className = '';
    $('pause').textContent = 'Pause';
    $('mode-note').textContent = mode === 'human'
        ? 'Use ↑ to thrust and ← / → to turn. Land on the orange pad before running out of fuel.'
        : 'The network supplies thrust and turn controls. The game handles movement and landing checks.';
    updateReadout();
}

function updateReadout() {
    $('clock').textContent = (frame/scenario.fps).toFixed(2)+' s';
    const name = mode === 'human' ? 'Manual flight' : mode === 'trained' ? 'Trained flight' : 'Untrained flight';
    $('status').textContent = Game.gameover ? (Lander.landed && !Lander.crashed ? 'Landed successfully' : 'Crashed') : paused ? 'Paused' : name;
    for (const key of ['left','up','right']) $(key+'-key').classList.toggle('on', Lander.pressed[key]);
}

Game.update = function(dt) {
    if (paused) return;
    if (Game.gameover) { originalUpdate(dt); return; }
    if (mode !== 'human') {
        const control = controlAt(policies[mode], frame);
        Lander.pressed = quantizer.next(control[0],control[1]);
    }
    originalUpdate(dt);
    history.push({frame,x:Lander.x,y:Lander.y,vx:Lander.v[0],vy:Lander.v[1],theta:Lander.theta,fuel:Lander.fuel});
    frame++;
    updateReadout();
    if (mode !== 'human' && frame > (scenario.horizon+3)*scenario.fps && !Game.gameover) {
        paused = true; $('status').textContent = 'Flight ended without landing';
    }
};

function setSpeed() {
    Game.slow = 1/Number($('speed').value);
    Game.slowStep = Game.step * Game.slow;
}

try {
    const [trained,untrained,metrics] = await Promise.all([
        fetch('results/trained.json').then(r=>{if(!r.ok)throw Error('Trained policy missing');return r.json()}),
        fetch('results/untrained.json').then(r=>r.json()),
        fetch('results/training.json').then(r=>r.json()),
    ]);
    policies = {trained,untrained}; scenario = trained.scenario;
    // Replays reset the state and reuse this game loop.
    Game.init($('canvas'), scenario.fps, scenario.level);
    reset('trained'); setSpeed();
    for (const id of ['trained','untrained','human','restart','pause']) $(id).disabled = false;
    $('trained').onclick = () => reset('trained');
    $('untrained').onclick = () => reset('untrained');
    $('human').onclick = () => reset('human');
    $('restart').onclick = () => reset();
    $('pause').onclick = () => {paused=!paused;$('pause').textContent=paused?'Resume':'Pause';updateReadout()};
    $('speed').onchange = setSpeed;
    $('training-badge').textContent = metrics.gpu ? 'Trained on '+metrics.gpu : 'Trained on '+metrics.device;
    $('training-summary').textContent = `Training took ${metrics.training_seconds.toFixed(1)} seconds: ${metrics.adam_steps} Adam steps, followed by ${metrics.lbfgs_closure_evaluations} L-BFGS evaluations.`;
    window.addEventListener('keydown', event => {if(['ArrowUp','ArrowLeft','ArrowRight'].includes(event.key))event.preventDefault()});
    window.pinnGame = {
        reset, history,
        get state() {return {mode,frame,paused,gameover:Game.gameover,landed:Lander.landed,crashed:Lander.crashed,x:Lander.x,y:Lander.y,speed:Lander.getVelocityModule(),fuel:Lander.fuel}},
        pause(value) {paused=value;updateReadout()},
    };
} catch(error) {
    $('status').textContent = 'Could not load the trained flight: '+error.message;
    console.error(error);
}
