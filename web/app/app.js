// Hash router, page shell and the on-request assistant.
import { h, t, getLang, setLang } from './ui.js';
import * as overview from './overview.js';
import * as controller from './controller.js';
import * as session from './session.js';
import * as research from './research.js';

const SCREENS = {
  overview: { mod: overview, label: () => t('Overview', 'Огляд') },
  controller: { mod: controller, label: () => t('Controller', 'Пульт') },
  session: { mod: session, label: () => t('Session', 'Сеанс') },
  research: { mod: research, label: () => t('Research', 'Дослідження') },
};

const app = document.getElementById('app');
let live = null;
let liveName = null;
let main = null;
let nav = null;

function parseHash() {
  const [name, param] = location.hash.slice(1).split('/');
  return SCREENS[name] ? { name, param } : { name: 'overview', param: undefined };
}

function assistant() {
  const log = h('div', { class: 'drawer-log', 'aria-live': 'polite' },
    h('p', { class: 'small' }, t('Ask about the simulator, the programs or the two scenarios. Answers do not come from a clinician.',
      'Запитайте про симулятор, програми чи два сценарії. Відповіді дає не лікар.')));
  const input = h('input', { type: 'text', id: 'ask', autocomplete: 'off' });
  const send = async (ev) => {
    ev.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    const you = h('p', { class: 'msg msg-you' }, q);
    const reply = h('p', { class: 'msg' }, t('Looking this up.', 'Шукаю відповідь.'));
    log.append(you, reply);
    try {
      const params = new URLSearchParams({ q, lang: getLang() === 'uk' ? 'ua' : 'en' });
      const res = await fetch(`/api/ask?${params}`);
      if (!res.ok) throw new Error(String(res.status));
      reply.textContent = (await res.json()).text;
    } catch (err) {
      reply.textContent = t('The assistant did not answer. Ask again in a moment.', 'Асистент не відповів. Запитайте ще раз за хвилину.');
    }
    log.scrollTop = log.scrollHeight;
  };
  const close = h('button', { class: 'btn', type: 'button', 'data-close': '1' }, t('Close', 'Закрити'));
  const dialog = h('dialog', { class: 'drawer', 'aria-labelledby': 'drawer-title' },
    h('div', { class: 'drawer-head' }, h('h2', { id: 'drawer-title' }, t('Assistant', 'Асистент')), close),
    log,
    h('form', { class: 'drawer-form', on: { submit: send } },
      h('label', { for: 'ask' }, t('Your question', 'Ваше запитання')), input,
      h('button', { class: 'btn btn-primary', type: 'submit' }, t('Ask', 'Запитати'))));
  close.addEventListener('click', () => dialog.close());
  return dialog;
}

function shell() {
  nav = h('nav', { class: 'nav', 'aria-label': t('Main', 'Головне') },
    Object.entries(SCREENS).map(([key, sc]) => h('a', { href: `#${key}`, 'data-nav': key }, sc.label())));
  const dialog = assistant();
  main = h('main', { id: 'main', tabindex: '-1' });
  app.replaceChildren(
    h('a', { class: 'skip', href: '#main', on: { click: (ev) => { ev.preventDefault(); main.focus(); } } },
      t('Skip to content', 'Перейти до вмісту')),
    h('p', { class: 'sim-band' }, t('Simulator. It connects to no real device and gives no medical advice.',
      'Симулятор. Не під’єднаний до жодного реального пристрою і не дає медичних порад.')),
    h('header', { class: 'top' },
      h('a', { class: 'brand', href: '#overview' }, 'Brain-Spine Orchestrator'),
      nav,
      h('div', { class: 'top-tools' },
        h('button', { class: 'btn', type: 'button', 'data-open-assistant': '1', on: { click: () => dialog.showModal() } }, t('Ask', 'Запитати')),
        h('button', {
          class: 'btn', type: 'button', 'data-lang': '1', lang: getLang() === 'uk' ? 'en' : 'uk',
          on: { click: () => { setLang(getLang() === 'uk' ? 'en' : 'uk'); boot(); } },
        }, getLang() === 'uk' ? 'English' : 'Українська'))),
    main,
    h('footer', { class: 'foot' },
      h('p', {}, t('All responses and body movement here are simulated. Numbers are illustrative and not clinically validated. The stimulation programs are published by Ihor Sharanda from his own device.',
        'Усі відповіді й рухи тіла тут симульовані. Числа ілюстративні й клінічно не підтверджені. Програми стимуляції опублікував Ігор Шаранда зі свого пристрою.'))),
    dialog);
  document.documentElement.lang = getLang();
}

function route() {
  const { name, param } = parseHash();
  if (live && liveName === name) {
    live.param?.(param);
    return;
  }
  live?.destroy?.();
  liveName = name;
  nav.querySelectorAll('[data-nav]').forEach((a) => {
    if (a.dataset.nav === name) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  live = SCREENS[name].mod.mount(main, param);
  document.title = `${SCREENS[name].label()}, Brain-Spine Orchestrator`;
  window.scrollTo(0, 0);
}

function boot() {
  live?.destroy?.();
  live = null;
  liveName = null;
  shell();
  route();
}

window.addEventListener('hashchange', route);
boot();
