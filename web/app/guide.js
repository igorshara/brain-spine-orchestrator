// Guided scenario: one sentence at a time, each step advances only when the replayed
// state says it happened, so a free click on the real controls advances it too.
import { h, t } from './ui.js';

export class Guide {
  constructor(host, sim, onReplay) {
    this.host = host;
    this.sim = sim;
    this.onReplay = onReplay;
    this.scenario = null;
    this.stepId = null;
    this.acted = false;
    this.count = 0;
  }

  load(scenario) {
    this.scenario = scenario;
    this.stepId = scenario.first;
    this.acted = false;
    this.count = 1;
    this.render();
    return this.sim.reset(scenario.setup, scenario.startAt ?? 3, 1);
  }

  update(state) {
    if (!this.scenario || !state) return;
    const step = this.scenario.steps[this.stepId];
    const next = step.go && step.go(state);
    if (next && next !== this.stepId) {
      this.stepId = next;
      this.acted = false;
      this.count += 1;
      this.render(true);
      this.update(state);
      return;
    }
    if (this.skipBtn) this.skipBtn.hidden = !(step.wait && this.sim.hasNext);
  }

  act(action) {
    this.acted = true;
    this.render();
    action.run(this.sim);
  }

  render(moved = false) {
    const step = this.scenario.steps[this.stepId];
    const hadFocus = this.host.contains(document.activeElement);
    const say = h('p', { class: 'guide-say', tabindex: '-1' }, step.say());
    const row = h('div', { class: 'guide-actions' });
    if (!this.acted || step.repeatable) {
      for (const action of step.actions || []) {
        row.append(h('button', {
          class: action.quiet ? 'btn' : 'btn btn-primary',
          type: 'button',
          on: { click: () => this.act(action) },
        }, action.label()));
      }
    }
    this.skipBtn = h('button', {
      class: 'btn', type: 'button', hidden: true, 'data-skip': '1', on: { click: () => this.sim.skip() },
    }, t('Skip to the next event', 'Перейти до наступної події'));
    row.append(this.skipBtn);
    if (step.end) {
      row.append(h('button', { class: 'btn', type: 'button', on: { click: () => this.onReplay() } },
        t('Play again', 'Програти ще раз')));
      if (step.end !== true) row.append(step.end());
    }
    this.host.replaceChildren(
      h('p', { class: 'guide-step' }, step.end ? t('Result', 'Результат') : t(`Step ${this.count}`, `Крок ${this.count}`)),
      say, row,
    );
    if (moved && hadFocus) say.focus();
    if (this.sim.state) {
      this.skipBtn.hidden = !(step.wait && this.sim.hasNext);
    }
  }
}
