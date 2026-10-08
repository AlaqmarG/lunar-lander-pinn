import assert from 'node:assert/strict';
import {Keys} from './controls.js';
for (const throttle of [0,.13,.5,.91,1]) for (const turn of [-1,-.73,0,.27,1]) {
    const keys = new Keys();
    let fuelFrames = 0, signedTurns = 0;
    for (let i=0;i<1000;i++) {
        const output = keys.next(throttle,turn);
        assert(!(output.left && output.right));
        fuelFrames += Number(output.up);
        signedTurns += Number(output.right)-Number(output.left);
    }
    assert(Math.abs(fuelFrames-1000*throttle)<=.500001);
    assert(Math.abs(signedTurns-1000*turn)<=.500001);
}
console.log('Thrust/rotation duty-cycle averages and mutually exclusive turns passed.');
