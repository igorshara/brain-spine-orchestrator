// Client side of the simulated patient link. The server replays the event log; this
// file only holds the log and the simulated clock, and never invents a device state.
const TICK_MS = 200;
const IDLE_SYNC_MS = 1000;

export class Sim {
  constructor(onChange) {
    this.onChange = onChange;
    this.events = [];
    this.now = 0;
    this.speed = 1;
    this.state = null;
    this.failed = false;
    this.inFlight = false;
    this.dirty = false;
    this.timer = null;
    this.lastWall = 0;
    this.lastSync = 0;
    this.seq = 0;
  }

  start() {
    if (this.timer) return;
    this.lastWall = performance.now();
    this.timer = setInterval(() => this.tick(), TICK_MS);
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
  }

  tick() {
    const wall = performance.now();
    if (!this.failed) this.now += ((wall - this.lastWall) / 1000) * this.speed;
    this.lastWall = wall;
    if (this.failed) return;
    const next = this.state && this.state.next_change_t;
    if ((next !== null && next !== undefined && this.now >= next) || wall - this.lastSync >= IDLE_SYNC_MS) {
      this.sync();
    }
  }

  reset(events = [], now = 0, speed = 1) {
    this.events = events.slice();
    this.now = now;
    this.speed = speed;
    this.state = null;
    this.failed = false;
    this.seq += 1;
    return this.sync();
  }

  push(event) {
    if (this.failed) return this.sync();
    this.events.push({ ...event, t: this.now });
    return this.sync();
  }

  // Jump to the moment the model says something changes next.
  skip() {
    const next = this.state && this.state.next_change_t;
    if (next === null || next === undefined) return Promise.resolve();
    this.now = Math.max(this.now, next + 0.01);
    return this.sync();
  }

  get hasNext() {
    const next = this.state && this.state.next_change_t;
    return next !== null && next !== undefined;
  }

  async sync() {
    if (this.inFlight) {
      this.dirty = true;
      return;
    }
    this.inFlight = true;
    this.lastSync = performance.now();
    const seq = this.seq;
    try {
      const res = await fetch('/api/link/replay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: this.events, now: this.now }),
      });
      if (!res.ok) throw new Error(`replay answered ${res.status}`);
      const state = await res.json();
      if (seq === this.seq) {
        this.state = state;
        this.failed = false;
      }
    } catch (err) {
      this.failed = true;
    }
    this.inFlight = false;
    this.onChange(this);
    if (this.dirty) {
      this.dirty = false;
      this.sync();
    }
  }
}

// A running stimulator with a confirmed status, the usual start of a scenario.
export const SWITCHED_ON = [{ t: 0, type: 'cmd', op: 'on' }];
