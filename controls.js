// Converts relaxed PINN controls to the existing game's original boolean keys.
export class Keys {
    constructor() { this.thrustError = 0; this.turnError = 0; }
    next(throttle, turn) {
        this.thrustError += Math.max(0, Math.min(1, throttle));
        const up = this.thrustError >= .5;
        if (up) this.thrustError -= 1;
        this.turnError += Math.max(-1, Math.min(1, turn));
        let direction = 0;
        if (this.turnError >= .5) { direction = 1; this.turnError -= 1; }
        else if (this.turnError <= -.5) { direction = -1; this.turnError += 1; }
        return {up, left: direction === -1, right: direction === 1};
    }
}

export function controlAt(policy, frame) {
    return policy.controls[Math.min(frame, policy.controls.length-1)];
}
