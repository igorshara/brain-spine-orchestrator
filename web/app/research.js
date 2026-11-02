import { h, t, getJSON, range } from './ui.js';
import { createWalker, loadMesh, jointAngles } from './walker.js';
import { lineChart, dataTable } from './chart.js';

const POLICY = [
  { key: 'none', color: '#1f6fd1', name: () => t('No guardian', 'Без охоронця') },
  { key: 'reactive', color: '#e0559a', name: () => t('Reactive', 'Реактивний') },
  { key: 'predictive', color: '#008300', name: () => t('Predictive', 'Прогнозний') },
];
const BANK_COLOR = { A: '#1f6fd1', B: '#e0559a', C: '#008300' };

const ARCHIVE = [
  ['flow', 'How it works', 'Як це працює'], ['approve', 'Clinician approval', 'Погодження лікаря'],
  ['frontier', 'Research frontier', 'Межа досліджень'], ['autoclin', 'Auto clinician report', 'Автозвіт лікарю'],
  ['urodyn', 'Urodynamics', 'Уродинаміка'], ['osim', 'OpenSim model', 'Модель OpenSim'],
  ['programs', 'Programs, full view', 'Програми, повний вигляд'], ['cockpit', 'Patient cockpit', 'Кабіна пацієнта'],
  ['plate', 'Electrode plate', 'Пластина електродів'], ['sensors', 'Sensors', 'Сенсори'],
  ['map', 'Auto-mapping (synthetic demo)', 'Автомапінг (синтетична демонстрація)'], ['guard', 'Autonomic guardian', 'Автономний охоронець'],
  ['auto', 'Bladder model', 'Модель сечового міхура'], ['autotrain', 'Scheduled training', 'Тренування за розкладом'],
  ['gym', 'Benchmark gym', 'Полігон порівнянь'], ['loco', 'Locomotion schematic', 'Схема локомоції'],
  ['shadow', 'Shadow mode', 'Тіньовий режим'], ['usedriven', 'Use-driven learning', 'Навчання від використання'],
  ['handpacer', 'Hand pacer', 'Ритм для руки'], ['duallock', 'Dual lock', 'Подвійне блокування'],
  ['balance', 'Balance', 'Рівновага'], ['reflex', 'Reflex', 'Рефлекс'],
];

const GOALS = {
  decrease_spasticity: ['Reduce spasticity', 'Зменшити спастику'],
  overnight: ['Overnight', 'На ніч'],
  pulling_up: ['Pulling up', 'Підтягування'],
  pushing: ['Pushing', 'Відштовхування'],
  standing: ['Standing', 'Стояння'],
  trunk: ['Trunk', 'Тулуб'],
  walking: ['Walking', 'Хода'],
};
const goalName = (goal) => (GOALS[goal] ? t(...GOALS[goal]) : goal);

function programPlot(programs) {
  const NS = 'http://www.w3.org/2000/svg';
  const s = (tag, attrs) => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  };
  let W = 640;
  const H = 300;
  const m = { l: 48, r: 16, t: 14, b: 40 };
  const minX = Math.floor(Math.min(...programs.map((p) => p.pw_us[0])) / 50) * 50 - 25;
  const maxX = Math.max(...programs.map((p) => p.pw_us[1])) + 25;
  const maxY = Math.max(...programs.map((p) => p.rate_hz[1])) * 1.05;
  const X = (v) => m.l + ((v - minX) / (maxX - minX)) * (W - m.l - m.r);
  const Y = (v) => H - m.b - (v / maxY) * (H - m.t - m.b);
  const svg = s('svg', { role: 'img', 'aria-label': t('Pulse width and rate ranges of each program', 'Діапазони ширини імпульсу й частоти кожної програми') });
  const tip = h('div', { class: 'chart-tip', hidden: true });
  const box = h('div', { class: 'chart-box' }, svg, tip);
  const yStep = [5, 10, 20, 25, 50, 100].find((v) => maxY / v <= 5) ?? 200;

  // Drawn at the real pixel width, so type stays one size at any screen width.
  function draw() {
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.replaceChildren();
    const xStep = [50, 100, 200, 250, 500].find((v) => (maxX - minX) / v <= (W < 480 ? 4 : 6)) ?? 1000;
    for (let v = 0; v <= maxY; v += yStep) {
      svg.append(s('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'grid' }));
      const l = s('text', { x: m.l - 6, y: Y(v) + 4, 'text-anchor': 'end', class: 'tick' });
      l.textContent = v;
      svg.append(l);
    }
    for (let v = Math.ceil(minX / xStep) * xStep; v <= maxX; v += xStep) {
      const l = s('text', { x: X(v), y: H - m.b + 16, 'text-anchor': 'middle', class: 'tick' });
      l.textContent = v;
      svg.append(l);
    }
    const xl = s('text', { x: W - m.r, y: H - 6, 'text-anchor': 'end', class: 'tick' });
    xl.textContent = t('Pulse width, µs', 'Ширина імпульсу, мкс');
    const yl = s('text', { x: m.l, y: m.t, class: 'tick' });
    yl.textContent = t('Rate, Hz', 'Частота, Гц');
    svg.append(xl, yl);
    for (const p of programs) {
      const x0 = X(p.pw_us[0]); const x1 = X(p.pw_us[1]);
      const y0 = Y(p.rate_hz[1]); const y1 = Y(p.rate_hz[0]);
      // A fixed range collapses to a point, which still needs a visible, hoverable mark.
      const w = Math.max(x1 - x0, 8); const ht = Math.max(y1 - y0, 8);
      const rect = s('rect', {
        x: x0 - (x1 - x0 < 8 ? 4 : 0), y: y0 - (y1 - y0 < 8 ? 4 : 0), width: w, height: ht, rx: 3,
        fill: BANK_COLOR[p.group], 'fill-opacity': 0.16, stroke: BANK_COLOR[p.group], 'stroke-width': 2, tabindex: 0, class: 'range',
      });
      const show = () => {
        tip.replaceChildren(h('strong', {}, `${p.slot} ${p.label}`),
          h('div', {}, `${t('Group', 'Група')} ${p.group}, ${range(p.pw_us)} µs, ${range(p.rate_hz)} Hz, ${t('amplitude', 'амплітуда')} ${range(p.amp)}`));
        tip.hidden = false;
        tip.style.left = `${Math.min(W < 480 ? 30 : 62, (x0 / W) * 100)}%`;
      };
      rect.addEventListener('pointerenter', show);
      rect.addEventListener('focus', show);
      rect.addEventListener('pointerleave', () => { tip.hidden = true; });
      rect.addEventListener('blur', () => { tip.hidden = true; });
      svg.append(rect);
    }
  }
  draw();
  new ResizeObserver(([e]) => {
    const next = Math.round(e.contentRect.width);
    if (next > 0 && next !== W) { W = next; requestAnimationFrame(draw); }
  }).observe(box);

  return h('figure', { class: 'chart' },
    h('figcaption', {}, t('Where my 20 programs sit', 'Де лежать мої 20 програм')),
    box,
    h('ul', { class: 'legend' }, Object.entries(BANK_COLOR).map(([bank, color]) => h('li', {},
      h('span', { class: 'swatch', style: `background:${color}` }), t(`Group ${bank}`, `Група ${bank}`)))),
    h('p', { class: 'chart-note' }, t(`Source: my own device, published by me. ${programs.length} programs. Each box spans the range a program allows.`,
      `Джерело: мій власний пристрій, опубліковано мною. ${programs.length} програм. Кожен прямокутник показує діапазон, який дозволяє програма.`)));
}

export function mount(root) {
  const stage = h('div', { class: 'stage-canvas stage-canvas-small', 'data-testid': 'research-walker' },
    h('p', { class: 'stage-wait', role: 'status' }, t('Loading the walking model', 'Завантажую модель ходи')));
  const slider = h('input', { type: 'range', min: 0, max: 59, value: 0, 'aria-label': t('Gait cycle frame', 'Кадр циклу ходи'), id: 'frame' });
  const playBtn = h('button', { class: 'btn', type: 'button' }, t('Pause', 'Пауза'));
  const gaitSlot = h('div', {});
  const guardSlot = h('div', { class: 'stack' }, h('p', { class: 'small' }, t('Running the simulation.', 'Виконується симуляція.')));
  const programSlot = h('div', {});
  let walker = null;
  let gone = false;
  let gaitChart = null;

  root.replaceChildren(h('div', { class: 'screen' },
    h('h1', {}, t('Under the hood', 'Під капотом')),
    h('p', { class: 'lead' }, t('The material behind the concept. Every result here is simulated or synthetic.',
      'Матеріал, що стоїть за концепцією. Кожен результат тут симульований або синтетичний.')),
    h('section', { class: 'panel' },
      h('h2', {}, t('Walking model', 'Модель ходи')),
      h('p', {}, t('Muscle-driven forward dynamics from OpenSim gait10dof18musc, 18 muscles. Drag through the gait cycle and the chart follows.',
        'М’язово-кероване моделювання в OpenSim gait10dof18musc, 18 м’язів. Протягніть цикл ходи, і графік іде слідом.')),
      h('div', { class: 'gait' },
        h('figure', { class: 'stage' }, stage,
          h('figcaption', {}, h('p', { class: 'stage-label' }, t('Simulated movement, not a treatment result', 'Симульований рух, а не результат лікування')))),
        h('div', {}, gaitSlot,
          h('div', { class: 'scrub' }, playBtn, h('label', { for: 'frame' }, t('Frame', 'Кадр')), slider)))),
    h('section', { class: 'panel' },
      h('h2', {}, t('Autonomic guardian, synthetic', 'Автономний охоронець, синтетичні дані')),
      h('p', {}, t('The same synthetic bladder filling under three policies. The reactive delay of 5 s is illustrative.',
        'Те саме синтетичне наповнення міхура за трьох стратегій. Затримка реактивної стратегії 5 с ілюстративна.')),
      guardSlot),
    h('section', { class: 'panel' },
      h('h2', {}, t('My programs', 'Мої програми')),
      h('p', { class: 'small' }, t('Published by Ihor, from his own device. Amplitude unit to confirm.', 'Опублікував Ігор зі свого пристрою. Одиницю амплітуди треба уточнити.')),
      programSlot),
    h('section', { class: 'panel' },
      h('h2', {}, t('Archive', 'Архів')),
      h('p', {}, t('The earlier research screens stay available as they were. They are in English and some use synthetic demonstrations.',
        'Попередні дослідницькі екрани лишаються доступними без змін. Вони англійською, частина використовує синтетичні демонстрації.')),
      h('ul', { class: 'archive' }, ARCHIVE.map(([id, en, uk]) => h('li', {}, h('a', { href: `/lab#${id}`, 'data-archive': id }, t(en, uk))))))));

  loadMesh().then((data) => {
    if (gone) return;
    const angles = jointAngles(data);
    const x = angles.map((_, i) => i);
    gaitChart = lineChart({
      title: t('Joint angles over the simulated run', 'Кути суглобів протягом симуляції'),
      unit: t('degrees', 'градуси'),
      xLabel: t('Frame', 'Кадр'),
      series: [
        { name: t('Right knee', 'Праве коліно'), color: '#1f6fd1', x, y: angles.map((a) => +a.kneeR.toFixed(1)) },
        { name: t('Left knee', 'Ліве коліно'), color: '#e0559a', x, y: angles.map((a) => +a.kneeL.toFixed(1)) },
        { name: t('Right hip', 'Праве стегно'), color: '#008300', x, y: angles.map((a) => +a.hipR.toFixed(1)) },
      ],
      source: t('Source: simulated OpenSim run, not a person.', 'Джерело: симуляція OpenSim, а не людина.'),
      baseline: { value: 0, label: t('Neutral joint, 0°', 'Нейтральний суглоб, 0°') },
      height: 240,
      onHover: (i) => { if (i !== null) { walker.pause(); walker.seek(i); syncPlay(); } },
    });
    gaitSlot.replaceChildren(gaitChart);
    slider.max = angles.length - 1;
    stage.replaceChildren();
    walker = createWalker(stage, data, {
      height: stage.clientHeight || 360,
      onFrame: (i) => { slider.value = i; gaitChart.mark(i); },
    });
    syncPlay();
  }).catch(() => {
    gaitSlot.textContent = t('The walking model did not load. Reload the page to try again.', 'Модель ходи не завантажилась. Оновіть сторінку.');
  });
  const syncPlay = () => { playBtn.textContent = walker?.playing ? t('Pause', 'Пауза') : t('Play', 'Грати'); };
  playBtn.addEventListener('click', () => { if (walker) { if (walker.playing) walker.pause(); else walker.play(); syncPlay(); } });
  slider.addEventListener('input', () => { if (walker) { walker.pause(); walker.seek(+slider.value); gaitChart?.mark(+slider.value); syncPlay(); } });

  getJSON('/api/guardian').then((data) => {
    if (gone) return;
    const panels = [];
    const seriesFor = (field) => POLICY.map((p) => ({
      name: p.name(), color: p.color, x: data[p.key].t, y: data[p.key][field],
    }));
    const sync = (i) => panels.forEach((c) => c.mark(i));
    const source = t('Source: synthetic model, no patient data.', 'Джерело: синтетична модель, без даних пацієнтів.');
    const m = data.none.metrics;
    const base = m.baseline_bp;
    panels.push(
      lineChart({ title: t('Blood pressure', 'Артеріальний тиск'), unit: 'mmHg', xLabel: t('Time, s', 'Час, с'), xUnit: ' s', series: seriesFor('bp'), source, baseline: { value: base, label: t(`Baseline, ${base} mmHg`, `Вихідний рівень, ${base} мм рт. ст.`) }, onHover: sync }),
      lineChart({ title: t('Bladder pressure', 'Тиск у міхурі'), unit: 'cmH2O', xLabel: t('Time, s', 'Час, с'), xUnit: ' s', series: seriesFor('pressure'), source, baseline: { value: m.ad_trigger_pressure, label: t(`Dysreflexia trigger, ${m.ad_trigger_pressure} cmH2O`, `Поріг дисрефлексії, ${m.ad_trigger_pressure} cmH2O`) }, onHover: sync }),
      lineChart({ title: t('Bladder volume', 'Об’єм міхура'), unit: 'mL', xLabel: t('Time, s', 'Час, с'), xUnit: ' s', series: seriesFor('volume'), source, baseline: { value: m.start_volume, label: t(`Starting volume, ${m.start_volume} mL`, `Початковий об’єм, ${m.start_volume} мл`) }, onHover: sync }),
    );
    const rows = POLICY.map((p) => {
      const m = data[p.key].metrics;
      return [p.name(), m.ad_episodes, m.ad_seconds_above_limit.toFixed(1), m.peak_bp_rise.toFixed(1), m.peak_pressure.toFixed(1)];
    });
    guardSlot.replaceChildren(...panels, h('div', { class: 'table-wrap' }, dataTable(
      t('Results at step 0.1 s. Synthetic, not clinically validated.', 'Результати з кроком 0,1 с. Синтетичні, клінічно не підтверджені.'),
      [t('Policy', 'Стратегія'), t('Episodes', 'Епізоди'), t('Seconds above limit', 'Секунд над межею'), t('Peak BP rise, mmHg', 'Найбільший ріст тиску, мм рт. ст.'), t('Peak bladder pressure', 'Найбільший тиск у міхурі')],
      rows)));
  }).catch(() => {
    guardSlot.textContent = t('The simulation did not run. Reload the page to try again.', 'Симуляція не запустилась. Оновіть сторінку.');
  });

  getJSON('/api/programs').then((d) => {
    if (gone) return;
    programSlot.replaceChildren(programPlot(d.programs), h('details', { class: 'more' },
      h('summary', {}, t(`Show all ${d.programs.length} programs`, `Показати всі ${d.programs.length} програм`)),
      h('div', { class: 'table-wrap' }, dataTable(
      t('All programs', 'Усі програми'),
      [t('Program', 'Програма'), t('Group', 'Група'), t('Goal', 'Мета'), t('Pulse width, µs', 'Ширина імпульсу, мкс'), t('Rate, Hz', 'Частота, Гц'), t('Amplitude, unit to confirm', 'Амплітуда, одиницю уточнити')],
      d.programs.map((p) => [`${p.slot} ${p.label}`, p.group, goalName(p.goal), range(p.pw_us), range(p.rate_hz), range(p.amp)])))));
  }).catch(() => {
    programSlot.textContent = t('Programs did not load. Reload the page to try again.', 'Програми не завантажились. Оновіть сторінку.');
  });

  return { destroy() { gone = true; walker?.destroy(); } };
}
