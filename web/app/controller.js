import { createTrace } from './trace.js';
import { h, t, ago, clock, getJSON, range } from './ui.js';
import { Sim, SWITCHED_ON, pausedNotice } from './link.js';
import { Guide } from './guide.js';

const off = (sim) => sim.push({ type: 'cmd', op: 'off' });
const setLink = (sim, mode) => sim.push({ type: 'link', mode });
const offFailedOver = (mode, sim) => { setLink(sim, mode); off(sim); };
const anyPending = (st) => st.controller.pending;
const restoreAction = {
  label: () => t('Restore the link', 'Відновити зв’язок'),
  run: (sim) => setLink(sim, 'good'),
};

export const SCENARIOS = {
  normal: {
    name: () => t('Normal', 'Звичайно'),
    setup: SWITCHED_ON,
    first: 'press',
    steps: {
      press: {
        say: () => t('The stimulator is on and both sides agree. Press Switch off.',
          'Стимулятор увімкнений, обидві сторони згодні. Натисніть «Вимкнути».'),
        actions: [{ label: () => t('Switch off', 'Вимкнути'), run: off }],
        go: (st) => (st.controller.state === 'off' ? 'done' : null),
      },
      done: {
        say: () => t('Requested, then acknowledged. The word Off appears only after the implant answers.',
          'Запит, потім підтвердження. Слово «Вимкнено» з’являється лише після відповіді імпланта.'),
        end: true,
      },
    },
  },
  reply: {
    name: () => t('Reply lost', 'Втрачена відповідь'),
    setup: SWITCHED_ON,
    first: 'press',
    steps: {
      press: {
        say: () => t('This time the command will arrive but the answer will not. Press Switch off.',
          'Цього разу команда дійде, а відповідь ні. Натисніть «Вимкнути».'),
        actions: [{ label: () => t('Switch off', 'Вимкнути'), run: (sim) => offFailedOver('lost_after', sim) }],
        go: (st) => (anyPending(st) ? 'wait' : null),
      },
      wait: {
        say: () => t('The controller waits for an answer. Look at the two sides.', 'Пульт чекає на відповідь. Подивіться на обидві сторони.'),
        wait: true,
        go: (st) => (st.controller.state === 'unknown' ? 'unknown' : null),
      },
      unknown: {
        say: () => t('The controller says Unknown, and it is right to. The implant has already stopped, but nothing told the controller.',
          'Пульт каже «Невідомо», і це чесно. Імплант уже зупинився, але пульт про це не дізнався.'),
        actions: [restoreAction],
        wait: true,
        go: (st) => (st.controller.state === 'off' ? 'done' : null),
      },
      done: {
        say: () => t('The link returned, the controller asked for the status, and Off is now confirmed.',
          'Зв’язок повернувся, пульт запитав стан, і тепер «Вимкнено» підтверджено.'),
        end: true,
      },
    },
  },
  command: {
    name: () => t('Command lost', 'Втрачена команда'),
    setup: SWITCHED_ON,
    first: 'press',
    steps: {
      press: {
        say: () => t('Now the command itself will be lost. Press Switch off.', 'Тепер загубиться сама команда. Натисніть «Вимкнути».'),
        actions: [{ label: () => t('Switch off', 'Вимкнути'), run: (sim) => offFailedOver('lost_before', sim) }],
        go: (st) => (anyPending(st) ? 'wait' : null),
      },
      wait: {
        say: () => t('The controller waits exactly as it did before.', 'Пульт чекає так само, як і минулого разу.'),
        wait: true,
        go: (st) => (st.controller.state === 'unknown' ? 'unknown' : null),
      },
      unknown: {
        say: () => t('The controller screen is the same as in the last case, yet the implant is still stimulating. This is why a lost connection must never be shown as Off.',
          'Екран пульта такий самий, як у попередньому випадку, але імплант усе ще стимулює. Саме тому втрата зв’язку ніколи не має виглядати як «Вимкнено».'),
        actions: [restoreAction],
        wait: true,
        go: (st) => (st.controller.state === 'off' ? 'done' : null),
      },
      done: {
        say: () => t('When the link returned, the controller sent Switch off again by itself. Only Switch off is resent automatically.',
          'Коли зв’язок повернувся, пульт сам повторив «Вимкнути». Автоматично повторюється лише вимкнення.'),
        end: true,
      },
    },
  },
  refused: {
    name: () => t('Refused', 'Відмова'),
    setup: SWITCHED_ON,
    first: 'press',
    steps: {
      press: {
        say: () => t('The implant will answer, but it will refuse the change. Press Increase.',
          'Імплант відповість, але відмовить у зміні. Натисніть «Збільшити».'),
        actions: [{
          label: () => t('Increase', 'Збільшити'),
          run: (sim) => { setLink(sim, 'refused'); sim.push({ type: 'cmd', op: 'amp_up' }); },
        }],
        go: (st) => (st.commands.some((c) => c.state === 'failed') ? 'done' : null),
      },
      done: {
        say: () => t('A refusal is an answer, so the state stays known. The command is marked Failed and the amplitude has not changed.',
          'Відмова теж відповідь, тому стан лишається відомим. Команда позначена як «Не виконано», амплітуда не змінилась.'),
        end: true,
      },
    },
  },
  home: {
    name: () => t('Left remote at home', 'Пульт удома'),
    setup: SWITCHED_ON,
    first: 'leave',
    steps: {
      leave: {
        say: () => t('You leave home with the stimulator on. The remote stays on the table.',
          'Ви виходите з дому з увімкненим стимулятором. Пульт лишається на столі.'),
        actions: [{ label: () => t('Leave home', 'Вийти з дому'), run: (sim) => sim.push({ type: 'leave_home' }) }],
        go: (st) => (!st.link.primary_present ? 'walk' : null),
      },
      walk: {
        say: () => t('You are walking away. Today, nothing would notice.', 'Ви віддаляєтесь. Сьогодні цього ніщо не помітить.'),
        wait: true,
        go: (st) => (st.link.leave_alert ? 'alert' : null),
      },
      alert: {
        say: () => t('One minute later your phone tells you: the remote is no longer with you. You can still turn around, or use a backup your clinic authorised in advance.',
          'За хвилину телефон повідомляє: пульта з вами немає. Ще можна повернутись або підключити запасний, наперед дозволений клінікою.'),
        actions: [
          { label: () => t('Pair the backup controller', 'Підключити запасний пульт'), run: (sim) => sim.push({ type: 'backup_pair' }) },
          { label: () => t('Go back for it', 'Повернутись по пульт'), quiet: true, run: (sim) => sim.push({ type: 'go_back' }) },
        ],
        go: (st) => (st.link.primary_present ? 'returned' : st.link.backup !== 'none' ? 'pairing' : null),
      },
      returned: {
        say: () => t('You turned back within a minute of leaving instead of finding out days later.',
          'Ви повернулись за хвилину після виходу, а не дізнались про це через кілька днів.'),
        end: true,
      },
      pairing: {
        say: () => t('The backup pairs and asks the implant for its status.', 'Запасний пульт підключається і запитує в імпланта стан.'),
        wait: true,
        go: (st) => (st.link.backup === 'active' ? 'backup' : null),
      },
      backup: {
        say: () => t('The backup can switch off, and that is all it can do. Try Increase, then Switch off.',
          'Запасний пульт уміє вимикати, і це все, що він може. Спробуйте «Збільшити», потім «Вимкнути».'),
        repeatable: true,
        actions: [
          { label: () => t('Increase', 'Збільшити'), quiet: true, run: (sim) => sim.push({ type: 'cmd', op: 'amp_up' }) },
          { label: () => t('Switch off', 'Вимкнути'), run: off },
        ],
        go: (st) => (st.controller.state === 'off' ? 'done' : null),
      },
      done: {
        say: () => t('The stimulator is off, confirmed, on the same day. You do not wait five or six days for a remote.',
          'Стимулятор вимкнено і підтверджено в той самий день. Не треба чекати пульт п’ять-шість днів.'),
        end: true,
      },
    },
  },
};

const STATE_WORD = {
  on: () => t('On', 'Увімкнено'),
  off: () => t('Off', 'Вимкнено'),
  unknown: () => t('Unknown', 'Невідомо'),
};
const OP = {
  on: () => t('Switch on', 'Увімкнути'),
  off: () => t('Switch off', 'Вимкнути'),
  program: () => t('Change program', 'Змінити програму'),
  amp_up: () => t('Increase', 'Збільшити'),
  amp_down: () => t('Decrease', 'Зменшити'),
};
const CMD_STATE = {
  requested: () => t('Requested', 'Запит надіслано'),
  acknowledged: () => t('Acknowledged', 'Підтверджено'),
  failed: () => t('Failed', 'Не виконано'),
  unknown: () => t('Unknown', 'Невідомо'),
};
const CMD_MARK = { requested: '○', acknowledged: '✓', failed: '✕', unknown: '?' };
export const REASON = {
  no_controller: () => t('No controller with you', 'Пульта з вами немає'),
  state_unknown: () => t('State unknown, only Switch off is allowed', 'Стан невідомий, дозволено лише вимкнення'),
  command_pending: () => t('Still waiting for the last command', 'Ще чекаємо на попередню команду'),
  already_on: () => t('Already on', 'Уже увімкнено'),
  backup_limited: () => t('The backup controller cannot change amplitude', 'Запасний пульт не змінює амплітуду'),
  not_on: () => t('The stimulator is off', 'Стимулятор вимкнено'),
  at_clinician_limit: () => t('At the limit your clinician set', 'Це межа, задана лікарем'),
  implant_refused: () => t('The implant refused', 'Імплант відмовив'),
  not_delivered: () => t('Not delivered', 'Не доставлено'),
  safety_blocked: () => t('Blocked by the safety layer', 'Заблоковано шаром безпеки'),
  safety_clamped: () => t('Limited by the safety layer', 'Обмежено шаром безпеки'),
  confirmed_after_reconnect: () => t('Confirmed after the link returned', 'Підтверджено після відновлення зв’язку'),
};

function homeTimeline() {
  const day = (label) => h('span', { class: 'tl-day' }, label);
  return h('section', { class: 'timeline', 'aria-label': t('Timeline of a forgotten remote', 'Хронологія забутого пульта') },
    h('h3', {}, t('The same day, two ways', 'Той самий день, два варіанти')),
    h('div', { class: 'tl-scale' }, [0, 1, 2, 3, 4, 5, 6].map((d) => day(t(`Day ${d}`, `День ${d}`)))),
    h('div', { class: 'tl-lane' },
      h('p', { class: 'tl-name' }, t('What happened to me', 'Як було в мене')),
      h('div', { class: 'tl-track' }, h('div', { class: 'tl-bar tl-bar-wait', style: 'width:92%' },
        t('Waiting for the remote, 5 to 6 days', 'Чекаю на пульт, 5–6 днів')))),
    h('div', { class: 'tl-lane' },
      h('p', { class: 'tl-name' }, t('With this concept', 'З цією концепцією')),
      h('div', { class: 'tl-track' }, h('div', { class: 'tl-bar tl-bar-fix', style: 'width:3%' }),
        h('span', { class: 'tl-note' }, t('Alert in a minute, backup the same day', 'Сповіщення за хвилину, запасний пульт того ж дня')))),
    h('p', { class: 'small' }, t('Timing in the concept lane is illustrative. The concept is not a feature of any existing system.',
      'Час у рядку концепції ілюстративний. Концепція не є функцією жодної наявної системи.')));
}

export function mount(root, param) {
  const sim = new Sim(() => update());
  const guideHost = h('div', { class: 'guide', 'aria-live': 'polite' });
  const guide = new Guide(guideHost, sim, () => play(current));
  let current = SCENARIOS[param] ? param : 'normal';
  let programs = [];

  const strip = h('div', { class: 'strip', role: 'group', 'aria-label': t('Scenarios', 'Сценарії') });
  for (const [key, sc] of Object.entries(SCENARIOS)) {
    strip.append(h('button', {
      type: 'button', class: 'chip', 'data-scenario': key, on: { click: () => { location.hash = `#controller/${key}`; } },
    }, sc.name()));
  }

  const word = h('p', { class: 'status-word', 'data-testid': 'controller-state' });
  const detail = h('p', { class: 'status-detail' });
  const truthWord = h('p', { class: 'truth-word', 'data-testid': 'implant-state' });
  const truthDetail = h('p', { class: 'status-detail' });
  const laneOut = h('div', { class: 'lane' }, h('span', { class: 'lane-name' }, t('Command', 'Команда')), h('span', { class: 'lane-line' }));
  const laneBack = h('div', { class: 'lane' }, h('span', { class: 'lane-name' }, t('Answer', 'Відповідь')), h('span', { class: 'lane-line' }));
  const wireNote = h('p', { class: 'wire-note' });

  const btn = (label, op) => h('button', {
    class: `btn ${op === 'off' ? 'btn-off' : ''}`, type: 'button', 'data-op': op,
    on: { click: () => sim.push({ type: 'cmd', op }) },
  }, label);
  const refusal = h('p', { class: 'refusal', role: 'status' });
  const ledger = h('tbody', {});
  const simClock = h('span', { class: 'clock' });
  const paused = pausedNotice(sim, () => play(current));
  const speeds = h('div', { class: 'speeds', role: 'group', 'aria-label': t('Simulation speed', 'Швидкість симуляції') },
    [1, 60, 600].map((v) => h('button', {
      class: 'chip', type: 'button', 'data-speed': v, on: { click: () => { sim.speed = v; update(); } },
    }, `${v}×`)));
  const progList = h('div', { class: 'programs' });
  const timelineSlot = h('div', {});
  const twin = h('div', { class: 'twin' },
    h('section', { class: 'side side-knows' },
      h('h2', {}, t('What the controller knows', 'Що знає пульт')), word, detail),
    h('div', { class: 'wire', 'data-testid': 'wire' }, laneOut, laneBack, wireNote),
    h('section', { class: 'side side-truth' },
      h('h2', {}, t('What the implant is actually doing', 'Що насправді робить імплант')), truthWord, truthDetail,
      h('p', { class: 'small' }, t('The simulator’s view. No real system can show this.', 'Погляд симулятора. Жодна реальна система цього не покаже.'))));

  const trace = createTrace(sim);
  const free = (label, ev) => h('button', { class: 'btn', type: 'button', on: { click: () => sim.push(ev) } }, label);

  root.replaceChildren(h('div', { class: 'screen' },
    h('h1', {}, t('A controller that never guesses', 'Пульт, який ніколи не вгадує')),
    h('p', { class: 'lead' }, t('It shows only what the implant has confirmed. When it cannot know, it says so.',
      'Він показує лише те, що підтвердив імплант. Коли знати неможливо, він так і каже.')),
    strip, guideHost, paused, twin, timelineSlot, trace.node,
    h('section', { class: 'panel controls' },
      h('h2', {}, t('Controls', 'Керування')),
      h('div', { class: 'control-row' },
        btn(t('Switch on', 'Увімкнути'), 'on'), btn(t('Switch off', 'Вимкнути'), 'off'),
        btn(t('Decrease', 'Зменшити'), 'amp_down'), btn(t('Increase', 'Збільшити'), 'amp_up')),
      refusal,
      h('div', { class: 'clock-row' },
        h('span', {}, t('Simulated time ', 'Час симуляції '), simClock), speeds)),
    h('section', { class: 'panel' },
      h('h2', {}, t('Command history', 'Історія команд')),
      h('table', { class: 'data ledger' },
        h('thead', {}, h('tr', {}, [t('Time', 'Час'), t('Command', 'Команда'), t('Status', 'Стан'), t('Note', 'Примітка')]
          .map((c) => h('th', { scope: 'col' }, c)))), ledger)),
    h('section', { class: 'panel' },
      h('h2', {}, t('My programs', 'Мої програми')),
      h('p', { class: 'small' }, t('Published by Ihor, from his own device. Responses here are simulated. Amplitude unit to confirm.',
        'Опублікував Ігор зі свого пристрою. Відповіді тут симульовані. Одиницю амплітуди треба уточнити.')),
      progList),
    h('details', { class: 'panel' },
      h('summary', {}, t('Try it yourself', 'Спробувати самому')),
      h('div', { class: 'control-row' },
        free(t('Link good', 'Зв’язок добрий'), { type: 'link', mode: 'good' }),
        free(t('Implant refuses', 'Імплант відмовляє'), { type: 'link', mode: 'refused' }),
        free(t('Commands get lost', 'Команди губляться'), { type: 'link', mode: 'lost_before' }),
        free(t('Answers get lost', 'Відповіді губляться'), { type: 'link', mode: 'lost_after' }),
        free(t('Leave home', 'Вийти з дому'), { type: 'leave_home' }),
        free(t('Go back', 'Повернутись'), { type: 'go_back' }),
        free(t('Pair the backup controller', 'Підключити запасний пульт'), { type: 'backup_pair' })))));

  function renderPrograms() {
    const byBank = { A: [], B: [], C: [] };
    programs.forEach((p, i) => byBank[p.group].push([p, i]));
    progList.replaceChildren(...Object.entries(byBank).map(([bank, rows]) => h('div', { class: 'bank' },
      h('h3', {}, t(`Group ${bank}`, `Група ${bank}`)),
      rows.map(([p, i]) => h('button', {
        class: 'prog', type: 'button', 'data-pid': `${p.slot}:${i}`,
        on: { click: () => sim.push({ type: 'cmd', op: 'program', program: `${p.slot}:${i}` }) },
      },
      h('span', { class: 'prog-name' }, `${p.slot} ${p.label}`),
      h('span', { class: 'prog-values' }, `${range(p.pw_us)} µs, ${range(p.rate_hz)} Hz, ${range(p.amp)}`))))));
  }

  const programName = (pid) => {
    const p = programs[+String(pid).split(':')[1]];
    return p ? `${p.slot} ${p.label}` : '';
  };

  function update() {
    root.querySelectorAll('[data-scenario]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.scenario === current));
    root.querySelectorAll('[data-speed]').forEach((b) => b.setAttribute('aria-pressed', +b.dataset.speed === sim.speed));
    paused.refresh();
    twin.classList.toggle('is-stale', sim.failed);
    timelineSlot.replaceChildren();
    if (current === 'home') timelineSlot.append(homeTimelineNode);
    const st = sim.state;
    if (!st) return;
    guide.update(st);
    trace.update(st);
    if (sim.failed) {
      word.textContent = '';
      detail.textContent = '';
      truthWord.textContent = '';
      truthDetail.textContent = '';
      return;
    }
    const c = st.controller;
    word.textContent = STATE_WORD[c.state]();
    word.dataset.state = c.state;
    if (c.pending) {
      detail.textContent = t('Waiting for the implant to answer.', 'Чекаємо на відповідь імпланта.');
    } else if (c.state === 'unknown') {
      detail.textContent = c.last_confirmed_t === null
        ? t('Nothing confirmed yet. Do not assume it is off.', 'Нічого ще не підтверджено. Не вважайте, що він вимкнений.')
        : t(`Last confirmed ${ago(st.now - c.last_confirmed_t)} ago. Do not assume it is off.`,
          `Востаннє підтверджено ${ago(st.now - c.last_confirmed_t)} тому. Не вважайте, що він вимкнений.`);
    } else if (c.state === 'on') {
      detail.textContent = `${programName(c.program)}, ${t('amplitude', 'амплітуда')} ${c.amp}`;
    } else {
      detail.textContent = t('Confirmed by the implant.', 'Підтверджено імплантом.');
    }
    const m = st.implant_model;
    truthWord.textContent = m.on ? t('Stimulating', 'Стимулює') : t('Not stimulating', 'Не стимулює');
    truthWord.dataset.on = m.on;
    truthDetail.textContent = m.on ? `${programName(m.program)}, ${t('amplitude', 'амплітуда')} ${m.amp}` : '';

    const mode = st.link.mode;
    const absent = !st.link.primary_present && st.link.backup !== 'active';
    laneOut.classList.toggle('is-broken', absent || mode === 'lost_before');
    laneBack.classList.toggle('is-broken', absent || mode === 'lost_after');
    laneOut.classList.toggle('is-busy', c.pending);
    wireNote.textContent = absent
      ? t('No controller in range', 'Пульта поблизу немає')
      : st.link.backup === 'active' && !st.link.primary_present ? t('Backup controller connected', 'Підключено запасний пульт')
        : ({
          good: t('Link good', 'Зв’язок добрий'),
          refused: t('Link good, implant refuses', 'Зв’язок добрий, імплант відмовляє'),
          lost_before: t('Commands get lost', 'Команди губляться'),
          lost_after: t('Answers get lost', 'Відповіді губляться'),
        })[mode];

    simClock.textContent = clock(sim.now);
    const last = st.commands[st.commands.length - 1];
    refusal.textContent = last && last.reason && last.state === 'failed' ? REASON[last.reason]?.() ?? '' : '';
    root.querySelectorAll('[data-pid]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.pid === c.program));
    ledger.replaceChildren(...st.commands.slice(-8).reverse().map((cmd) => h('tr', { 'data-state': cmd.state },
      h('td', {}, clock(cmd.t)),
      h('td', {}, OP[cmd.op]?.() ?? cmd.op, cmd.auto ? t(' (automatic)', ' (автоматично)') : ''),
      h('td', { class: 'cmd-state' }, h('span', { 'aria-hidden': 'true' }, `${CMD_MARK[cmd.state]} `), CMD_STATE[cmd.state]()),
      h('td', {}, cmd.reason ? (REASON[cmd.reason]?.() ?? '') : ''))));
    if (!st.commands.length) {
      ledger.replaceChildren(h('tr', {}, h('td', { colspan: 4 }, t('No commands yet.', 'Команд ще немає.'))));
    }
  }

  const homeTimelineNode = homeTimeline();

  function play(key) {
    current = key;
    guide.load(SCENARIOS[key]);
    update();
  }

  getJSON('/api/programs').then((d) => { programs = d.programs; renderPrograms(); update(); })
    .catch(() => { progList.textContent = t('Programs did not load. Reload the page to try again.', 'Програми не завантажились. Оновіть сторінку.'); });
  sim.start();
  play(current);

  return {
    param(next) { if (SCENARIOS[next] && next !== current) play(next); },
    destroy() { sim.stop(); },
  };
}

