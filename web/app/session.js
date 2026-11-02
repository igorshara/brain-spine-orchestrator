import { createTrace } from './trace.js';
import { h, t, clock } from './ui.js';
import { Sim, SWITCHED_ON, pausedNotice } from './link.js';
import { Guide } from './guide.js';

const start = (sim, minutes) => sim.push({ type: 'reminder_start', minutes });
const ack = (sim, choice) => sim.push({ type: 'reminder_ack', choice });
const switchOffAction = { label: () => t('Switch off', 'Вимкнути'), run: (sim) => ack(sim, 'off') };

const SCENARIOS = {
  answered: {
    name: () => t('You answer', 'Ви відповідаєте'),
    setup: SWITCHED_ON,
    first: 'start',
    steps: {
      start: {
        say: () => t('You switch on and walk. Later you forget. Start a one hour reminder.',
          'Ви вмикаєте стимулятор і йдете. Згодом про це забуваєте. Запустіть нагадування на годину.'),
        actions: [{ label: () => t('Start a 1 hour reminder', 'Запустити нагадування на 1 годину'), run: (sim) => start(sim, 60) }],
        go: (st) => (st.reminder ? 'running' : null),
      },
      running: {
        say: () => t('The hour passes. Skip ahead rather than wait.', 'Година минає. Перейдіть уперед, щоб не чекати.'),
        wait: true,
        go: (st) => (st.reminder?.state === 'due' ? 'due' : null),
      },
      due: {
        say: () => t('The reminder asks one question. Answer it.', 'Нагадування ставить одне запитання. Дайте відповідь.'),
        actions: [switchOffAction],
        wait: false,
        go: (st) => (st.reminder?.state === 'closed' ? 'done' : null),
      },
      done: {
        say: () => t('Off is shown only after the implant confirmed it. The reminder is closed.',
          '«Вимкнено» з’являється лише після підтвердження імпланта. Нагадування закрито.'),
        end: true,
      },
    },
  },
  unanswered: {
    name: () => t('Nobody answers', 'Ніхто не відповідає'),
    setup: SWITCHED_ON,
    first: 'start',
    steps: {
      start: {
        say: () => t('This is the day I forgot. Start the reminder, then do not answer it.',
          'Це той день, коли я забув. Запустіть нагадування і не відповідайте.'),
        actions: [{ label: () => t('Start a 1 hour reminder', 'Запустити нагадування на 1 годину'), run: (sim) => start(sim, 60) }],
        go: (st) => (st.reminder ? 'running' : null),
      },
      running: {
        say: () => t('The hour passes.', 'Година минає.'),
        wait: true,
        go: (st) => (st.reminder?.state === 'due' ? 'due' : null),
      },
      due: {
        say: () => t('You do not see it. It asks again in five minutes.', 'Ви цього не бачите. За п’ять хвилин воно запитає знову.'),
        wait: true,
        go: (st) => (st.reminder?.notifications >= 2 ? 'repeat' : null),
      },
      repeat: {
        say: () => t('Still nothing. After fifteen minutes it tells someone you trust.',
          'Досі нічого. За п’ятнадцять хвилин воно повідомить людину, якій ви довіряєте.'),
        wait: true,
        go: (st) => (st.reminder?.escalated ? 'done' : null),
      },
      done: {
        say: () => t('Your trusted person now knows, in this simulation. Nothing is sent to anyone. On that day of mine this could have ended the long run early.',
          'Довірена людина тепер знає, у цій симуляції. Насправді нікому нічого не надсилається. Того мого дня це могло б раніше припинити довгу роботу стимулятора.'),
        end: true,
      },
    },
  },
  lost: {
    name: () => t('Connection lost', 'Зв’язок втрачено'),
    setup: SWITCHED_ON,
    first: 'start',
    steps: {
      start: {
        say: () => t('Start the reminder. The connection drops before it is due.',
          'Запустіть нагадування. Зв’язок зникне ще до його спрацювання.'),
        actions: [{
          label: () => t('Start a 1 hour reminder', 'Запустити нагадування на 1 годину'),
          run: (sim) => { start(sim, 60); sim.push({ type: 'link', mode: 'lost_before' }); },
        }],
        go: (st) => (st.reminder ? 'running' : null),
      },
      running: {
        say: () => t('The hour passes without a connection.', 'Година минає без зв’язку.'),
        wait: true,
        go: (st) => (st.reminder?.state === 'due' ? 'due' : null),
      },
      due: {
        say: () => t('The reminder still fires, because it lives on the phone. Try to switch off.',
          'Нагадування все одно спрацьовує, бо працює на телефоні. Спробуйте вимкнути.'),
        actions: [switchOffAction],
        go: (st) => (st.reminder?.state === 'off_requested' ? 'trying' : st.reminder?.state === 'off_unconfirmed' ? 'done' : null),
      },
      trying: {
        say: () => t('The command is on its way, and no answer is coming.', 'Команду надіслано, відповіді не буде.'),
        wait: true,
        go: (st) => (st.reminder?.state === 'off_unconfirmed' ? 'done' : null),
      },
      done: {
        say: () => t('The screen does not say Off. Treat the stimulator as still on and follow your clinic’s backup plan.',
          'Екран не каже «Вимкнено». Вважайте, що стимулятор усе ще працює, і дійте за резервним планом вашої клініки.'),
        end: true,
      },
    },
  },
};

const REMINDER_LINE = {
  running: () => t('Reminder running.', 'Нагадування запущено.'),
  due: () => t('Is the stimulator still meant to be on?', 'Стимулятор і досі має працювати?'),
  off_requested: () => t('Switch off requested. Waiting for the implant.', 'Вимкнення надіслано. Чекаємо на імплант.'),
  off_unconfirmed: () => t('Switch off not confirmed. Treat it as still on and follow your clinic’s backup plan.',
    'Вимкнення не підтверджено. Вважайте, що стимулятор працює, і дійте за резервним планом вашої клініки.'),
  off_failed: () => t('The implant refused to switch off. Follow your clinic’s backup plan.',
    'Імплант відмовився вимикатись. Дійте за резервним планом вашої клініки.'),
};

export function mount(root, param) {
  const sim = new Sim(() => update());
  const trace = createTrace(sim);
  const guideHost = h('div', { class: 'guide', 'aria-live': 'polite' });
  const guide = new Guide(guideHost, sim, () => play(current));
  let current = SCENARIOS[param] ? param : 'answered';

  const timer = h('p', { class: 'timer', 'data-testid': 'timer' }, '00:00:00');
  const line = h('p', { class: 'reminder-line', 'data-testid': 'reminder-line', role: 'status' });
  const known = h('strong', { 'data-testid': 'session-controller' });
  const truth = h('strong', { 'data-testid': 'session-implant' });
  const stepsTrack = h('ol', { class: 'track' });
  const choices = h('div', { class: 'control-row', hidden: true },
    h('button', { class: 'btn btn-off', type: 'button', on: { click: () => ack(sim, 'off') } }, t('Switch off', 'Вимкнути')),
    h('button', { class: 'btn', type: 'button', on: { click: () => ack(sim, 'snooze') } }, t('Snooze 15 min', 'Відкласти на 15 хв')),
    h('button', { class: 'btn', type: 'button', on: { click: () => ack(sim, 'keep') } }, t('Keep on', 'Залишити увімкненим')));
  const presets = h('div', { class: 'control-row' },
    [[30, t('30 min', '30 хв')], [60, t('1 hour', '1 година')], [120, t('2 hours', '2 години')]]
      .map(([m, label]) => h('button', { class: 'btn', type: 'button', 'data-preset': m, on: { click: () => start(sim, m) } }, label)));
  const auto = h('input', {
    type: 'checkbox', id: 'auto-rem',
    on: { change: () => sim.push({ type: 'settings', auto_reminder_min: auto.checked ? 60 : null }) },
  });
  const paused = pausedNotice(sim, () => play(current));

  const strip = h('div', { class: 'strip', role: 'group', 'aria-label': t('Scenarios', 'Сценарії') });
  for (const [key, sc] of Object.entries(SCENARIOS)) {
    strip.append(h('button', {
      type: 'button', class: 'chip', 'data-scenario': key, on: { click: () => { location.hash = `#session/${key}`; } },
    }, sc.name()));
  }
  const panel = h('section', { class: 'panel session-panel' },
    h('p', { class: 'timer-label' }, t('Time since you started this reminder', 'Час від запуску цього нагадування')),
    timer, stepsTrack, line, choices,
    h('p', { class: 'small' }, t('Controller: ', 'Пульт: '), known, t('. Implant, simulator’s view: ', '. Імплант, погляд симулятора: '), truth, '.'),
    h('p', { class: 'small' }, t('This is not a measure of how long stimulation has run. Nothing here knows that.',
      'Це не вимір тривалості стимуляції. Цього тут ніщо не знає.')));

  root.replaceChildren(h('div', { class: 'screen' },
    h('h1', {}, t('A reminder you cannot sleep through', 'Нагадування, яке не проґавиш')),
    h('p', { class: 'lead' }, t('You set it. If you do not answer, it asks again, and then it tells someone you trust.',
      'Ви його ставите. Якщо не відповідаєте, воно запитує знову, а потім повідомляє людину, якій ви довіряєте.')),
    strip, guideHost, paused, panel, trace.node,
    h('details', { class: 'panel' },
      h('summary', {}, t('Try it yourself', 'Спробувати самому')),
      h('h3', {}, t('Start a reminder', 'Запустити нагадування')), presets,
      h('p', {}, h('label', { for: 'auto-rem' }, auto, t(' Start a 1 hour reminder each time I switch on', ' Запускати нагадування на 1 годину при кожному увімкненні'))),
      h('div', { class: 'speeds', role: 'group', 'aria-label': t('Simulation speed', 'Швидкість симуляції') },
        [1, 60, 600].map((v) => h('button', { class: 'chip', type: 'button', 'data-speed': v, on: { click: () => { sim.speed = v; update(); } } }, `${v}×`))))));

  function update() {
    root.querySelectorAll('[data-scenario]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.scenario === current));
    root.querySelectorAll('[data-speed]').forEach((b) => b.setAttribute('aria-pressed', +b.dataset.speed === sim.speed));
    paused.refresh();
    panel.classList.toggle('is-stale', sim.failed);
    const st = sim.state;
    if (!st) return;
    guide.update(st);
    trace.update(st);
    if (sim.failed) {
      line.textContent = '';
      known.textContent = '';
      truth.textContent = '';
      return;
    }
    const r = st.reminder;
    timer.textContent = r ? clock(r.elapsed_s) : '00:00:00';
    timer.dataset.state = r ? r.state : 'none';
    const closedLine = r?.outcome === 'off_confirmed'
      ? t('Stimulator off, confirmed by the implant.', 'Стимулятор вимкнено, імплант підтвердив.')
      : t('You chose to keep it on. The reminder is closed.', 'Ви вирішили залишити увімкненим. Нагадування закрито.');
    line.textContent = !r ? t('No reminder running.', 'Нагадування не запущено.')
      : r.state === 'closed' ? closedLine : REMINDER_LINE[r.state]();
    choices.hidden = !(r && r.state === 'due');
    known.textContent = { on: t('on', 'увімкнено'), off: t('off', 'вимкнено'), unknown: t('unknown', 'невідомо') }[st.controller.state];
    truth.textContent = st.implant_model.on ? t('stimulating', 'стимулює') : t('not stimulating', 'не стимулює');
    const reached = [
      [t('Started', 'Запущено'), !!r],
      [t('Asked', 'Запитано'), !!r && r.notifications >= 1],
      [t('Asked again', 'Запитано вдруге'), !!r && r.notifications >= 2],
      [t('Trusted person told', 'Повідомлено довірену людину'), !!r && r.escalated],
    ];
    stepsTrack.replaceChildren(...reached.map(([label, done]) => h('li', { class: done ? 'is-done' : '' }, label)));
  }

  function play(key) {
    current = key;
    guide.load(SCENARIOS[key]);
    update();
  }

  sim.start();
  play(current);
  return {
    param(next) { if (SCENARIOS[next] && next !== current) play(next); },
    destroy() { sim.stop(); },
  };
}
