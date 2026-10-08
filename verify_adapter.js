// Executes watch.js + original Game in a minimal DOM harness (not a browser).
// Captures original Canvas drawing calls when browser spawning is unavailable.
import fs from 'node:fs';
import assert from 'node:assert/strict';

class CanvasCalls {
    constructor(){this.operations=[];this.fillStyle='#000';this.strokeStyle='#000';this.lineWidth=1;this.globalAlpha=1}
    clearRect(){this.operations=[]}
    beginPath(){this.points=[];this.circle=null}
    moveTo(x,y){this.points.push([x,y])}
    lineTo(x,y){this.points.push([x,y])}
    arc(x,y,r,start,end){assert(Math.abs(end-start-2*Math.PI)<1e-9);this.circle=[x,y,r]}
    createRadialGradient(...args){return {gradient:args,stops:[],addColorStop(at,color){this.stops.push([at,color])}}}
    fill(){this.operations.push({kind:this.circle?'circle':'polygon',geometry:this.circle||this.points,fill:this.fillStyle,alpha:this.globalAlpha})}
    stroke(){this.operations.push({kind:'line',geometry:this.points,stroke:this.strokeStyle,width:this.lineWidth,alpha:this.globalAlpha})}
}
const statsContext={fillRect(){},fillText(){},drawImage(){}};
const canvasCalls=new CanvasCalls();
class Element {
    constructor(id=''){this.id=id;this.style={};this.children=[];this.innerHTML='';this.textContent='';this.className='';this.disabled=false;this.value='2';this.width=800;this.height=600;this.classList={toggle(){}}}
    appendChild(child){this.children.push(child)}
    addEventListener(){}
    getContext(){return this.id==='canvas'?canvasCalls:statsContext}
}
const ids=new Map(),listeners=new Map(),raf=[];
globalThis.document={getElementById(id){if(!ids.has(id))ids.set(id,new Element(id));return ids.get(id)},createElement(){return new Element()},body:new Element()};
globalThis.window={devicePixelRatio:1,addEventListener(name,fn){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(fn)},requestAnimationFrame(fn){raf.push(fn)}};
globalThis.self={performance};
globalThis.fetch=async url=>{
    const file=new URL(url,import.meta.url);
    const content=fs.readFileSync(file,'utf8');
    return {ok:true,json:async()=>JSON.parse(content)};
};
await import('./watch.js');
const {default:Game}=await import('./third_party/lunar_lander/js/game.js');
assert(window.pinnGame,'Adapter failed to initialize');
assert.equal(raf.length,1,'Expected one original game loop');
const captures=[];
window.pinnGame.reset('trained');
window.pinnGame.pause(true);
function capture(){Game.render(0);captures.push({state:window.pinnGame.state,operations:JSON.parse(JSON.stringify(canvasCalls.operations)),ui:Object.fromEntries(['level','fuel','velocity','angle'].map(id=>[id,ids.get(id).innerHTML]))})}
capture();
window.pinnGame.pause(false);
for(let i=0;i<1000&&!window.pinnGame.state.gameover;i++){
    Game.update(Game.step);
    if(i%6===5||window.pinnGame.state.gameover)capture();
}
const trained=window.pinnGame.state;
assert(trained.landed&&!trained.crashed);
assert(ids.get('gameover').innerHTML.includes('You Landed!'));
window.pinnGame.pause(true);
const pausedFrame=window.pinnGame.state.frame;Game.update(Game.step);assert.equal(window.pinnGame.state.frame,pausedFrame);
function run(mode){window.pinnGame.reset(mode);window.pinnGame.pause(false);for(let i=0;i<1000&&!window.pinnGame.state.gameover;i++)Game.update(Game.step);window.pinnGame.pause(true);return window.pinnGame.state}
const restart=run('trained'),untrained=run('untrained');
assert(restart.landed&&!restart.crashed&&restart.frame===trained.frame);
assert(untrained.crashed&&!untrained.landed);
ids.get('human').onclick();
for(const callback of listeners.get('keydown'))callback({keyCode:38,key:'ArrowUp',preventDefault(){}});
Game.update(Game.step);
const human=window.pinnGame.state;assert(human.mode==='human'&&human.fuel===1999);
for(const callback of listeners.get('keyup'))callback({keyCode:38,key:'ArrowUp'});
assert.equal(raf.length,1,'Restart created multiple loops');
const node=JSON.parse(fs.readFileSync(new URL('./results/trained-game-replay.json',import.meta.url)));
assert.equal(trained.frame,node.physics_frames);
assert(Math.abs(trained.x-node.contact_x)<1e-10);
assert(Math.abs(trained.y-node.contact_y)<1e-10);
fs.writeFileSync(new URL('./results/render-calls.json',import.meta.url),JSON.stringify(captures));
const result={validation:'Node DOM/Canvas harness; not a launched browser',trained,restart,untrained,human_key_applied:true,pause_checked:true,one_game_loop:true,agrees_with_original_engine_replay:true,canvas_captures:captures.length};
fs.writeFileSync(new URL('./results/adapter-validation.json',import.meta.url),JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
