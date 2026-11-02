// Run trace: what the screen said against what the implant did, from the replayed timeline.
import { clock, h, t } from './ui.js';

const CONTROLLER = {
  on: () => t('On', 'Увімкнено'),
  off: () => t('Off', 'Вимкнено'),
  unknown: () => t('Unknown', 'Невідомо'),
  wait: () => t('Waiting for the answer', 'Чекає на відповідь'),
};
const implantWord = (on) => (on ? t('Stimulating', 'Стимулює') : t('Not stimulating', 'Не стимулює'));
const disagrees = (r) => r.controller === 'unknown' || (r.controller === 'on') !== r.implant_on;
const screenKey = (r) => (r.pending ? 'wait' : r.controller);

export function createTrace(sim) {
  const sum = h('p', { class: 'trace-sum', 'data-testid': 'trace-sum', role: 'status' });
  const screen = h('div', { class: 'trace-track', 'data-testid': 'trace-screen' });
  const implant = h('div', { class: 'trace-track', 'data-testid': 'trace-implant' });
  const apart = h('div', { class: 'trace-track trace-track-thin', 'data-testid': 'trace-apart' });
  const axis = h('div', { class: 'trace-axis' });
  const rows = h('tbody', {});
  let latest = null;

  const download = () => {
    const run = {
      note: 'Simulated run. Replaying events up to now through /api/link/replay gives the same state.',
      events: sim.events, now: sim.now, timeline: latest.timeline, commands: latest.commands, log: latest.log,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }));
    const a = h('a', { href: url, download: 'bso-simulated-run.json' });
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const swatch = (cls, label) => h('li', {}, h('span', { class: `seg ${cls}` }), label);
  const node = h('section', { class: 'panel trace', 'data-testid': 'trace' },
    h('div', { class: 'trace-head' }, h('h2', {}, t('This run, second by second', 'Цей запуск, секунда за секундою')), sum),
    h('div', { class: 'trace-grid' },
      h('p', { class: 'trace-name' }, t('The screen said', 'Екран казав')), screen,
      h('p', { class: 'trace-name' }, t('The implant did', 'Імплант робив')), implant,
      h('p', { class: 'trace-name' }, t('Out of step', 'Розходились')), apart,
      axis),
    h('ul', { class: 'trace-key' },
      swatch('seg-on', t('On or stimulating', 'Увімкнено або стимулює')),
      swatch('seg-off', t('Off', 'Вимкнено')),
      swatch('seg-wait', CONTROLLER.wait()),
      swatch('seg-unknown', CONTROLLER.unknown()),
      swatch('seg-apart', t('Out of step', 'Розходились'))),
    h('div', { class: 'trace-tools' },
      h('button', { class: 'btn', type: 'button', 'data-testid': 'trace-download', on: { click: download } }, t('Download this run', 'Завантажити цей запуск')),
      h('span', { class: 'small' }, t('Simulated. The same event log always replays to the same result.', 'Симуляція. Той самий журнал подій завжди дає той самий результат.')),
      h('details', {}, h('summary', {}, t('Show as a table', 'Показати таблицею')),
        h('table', { class: 'data trace-table' },
          h('thead', {}, h('tr', {}, [t('From', 'Від'), t('The screen said', 'Екран казав'), t('The implant did', 'Імплант робив')].map((c) => h('th', { scope: 'col' }, c)))),
          rows))));

  function paint(track, list, now, cls, title) {
    const span = Math.max(now, 1);
    const runs = [];
    list.forEach((r, i) => {
      const end = i + 1 < list.length ? list[i + 1].t : now;
      const c = cls(r);
      if (end <= r.t) return;
      const last = runs[runs.length - 1];
      if (last && last.c === c) last.end = end;
      else runs.push({ c, r, start: r.t, end });
    });
    track.replaceChildren(...runs.filter((run) => run.c).map((run) => h('span', {
      class: `seg ${run.c}`, title: `${clock(run.start)}: ${title(run.r)}`,
      style: `left:${(run.start / span) * 100}%;width:${((run.end - run.start) / span) * 100}%`,
    })));
  }

  function update(st) {
    latest = st;
    const list = st.timeline;
    const screenCls = { on: 'seg-on', off: 'seg-off', unknown: 'seg-unknown', wait: 'seg-wait' };
    paint(screen, list, st.now, (r) => screenCls[screenKey(r)], (r) => CONTROLLER[screenKey(r)]());
    paint(implant, list, st.now, (r) => (r.implant_on ? 'seg-on' : 'seg-off'), (r) => implantWord(r.implant_on));
    paint(apart, list, st.now, (r) => (disagrees(r) ? 'seg-apart' : null), () => t('Out of step', 'Розходились'));
    axis.replaceChildren(h('span', {}, clock(0)), h('span', {}, clock(st.now / 2)), h('span', {}, clock(st.now)));
    const apartFor = st.disagreement_s;
    sum.dataset.apart = apartFor >= 2;
    sum.textContent = t(`Out of step for ${clock(apartFor)} of ${clock(st.now)}`, `Розходились ${clock(apartFor)} із ${clock(st.now)}`);
    const said = list.filter((r, i) => i === 0 || screenKey(r) !== screenKey(list[i - 1]) || r.implant_on !== list[i - 1].implant_on);
    rows.replaceChildren(...said.slice(-40).map((r) => h('tr', {},
      h('td', { 'data-label': t('From', 'Від') }, clock(r.t)),
      h('td', { 'data-label': t('The screen said', 'Екран казав') }, CONTROLLER[screenKey(r)]()),
      h('td', { 'data-label': t('The implant did', 'Імплант робив') }, implantWord(r.implant_on)))));
  }

  return { node, update };
}
