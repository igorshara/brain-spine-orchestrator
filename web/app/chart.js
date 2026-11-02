// Line chart in plain SVG: one axis, recessive grid, crosshair with tooltip, direct labels.
import { h, t } from './ui.js';

const NS = 'http://www.w3.org/2000/svg';
const s = (tag, attrs) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
};

function ticks(min, max, count) {
  const span = max - min || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((m) => m >= raw);
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export function lineChart({ title, unit, xLabel, xUnit = '', series, source, height = 190, baseline = null, onHover = null, yMin = null }) {
  const wrap = h('figure', { class: 'chart' }, h('figcaption', {}, title));
  const box = h('div', { class: 'chart-box' });
  const tip = h('div', { class: 'chart-tip', hidden: true });
  box.append(tip);
  wrap.append(box);
  if (series.length >= 2) {
    wrap.append(h('ul', { class: 'legend' }, series.map((d) => h('li', {},
      h('span', { class: 'swatch', style: `background:${d.color}` }), d.name))));
  }

  let W = 640;
  const xs = series[0].x;
  const all = series.flatMap((d) => d.y);
  wrap.append(h('p', { class: 'chart-note' }, `${source} ${t(`${xs.length} samples per line.`, `${xs.length} точок на лінію.`)}`));
  wrap.append(numbers({ title, unit, xLabel, xs, series }));
  const lo = yMin !== null ? yMin : Math.min(...all, baseline?.value ?? Infinity);
  const hi = Math.max(...all, baseline?.value ?? -Infinity);
  const pad = (hi - lo) * 0.08 || 1;
  const y0 = yMin !== null ? yMin : lo - pad;
  const y1 = hi + pad;
  const m = { l: 44, r: 16, t: 10, b: 36 };
  const X = (v) => m.l + ((v - xs[0]) / (xs[xs.length - 1] - xs[0] || 1)) * (W - m.l - m.r);
  const Y = (v) => height - m.b - ((v - y0) / (y1 - y0)) * (height - m.t - m.b);

  const svg = s('svg', { role: 'img', 'aria-label': `${title}, ${unit}` });
  let cross = null;
  let marked = null;

  // Drawn at the real pixel width, so type stays one size at any screen width.
  function draw() {
    const labelled = series.length >= 2 && series.length <= 4 && W >= 480;
    m.r = labelled ? Math.max(...series.map((d) => d.name.length)) * 7 + 14 : 16;
    svg.setAttribute('viewBox', `0 0 ${W} ${height}`);
    svg.replaceChildren();
    for (const v of ticks(y0, y1, 4)) {
      svg.append(s('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'grid' }));
      const label = s('text', { x: m.l - 6, y: Y(v) + 4, 'text-anchor': 'end', class: 'tick' });
      label.textContent = v;
      svg.append(label);
    }
    for (const v of ticks(xs[0], xs[xs.length - 1], W < 480 ? 4 : 8)) {
      const label = s('text', { x: X(v), y: height - m.b + 16, 'text-anchor': 'middle', class: 'tick' });
      label.textContent = v;
      svg.append(label);
    }
    const axis = s('text', { x: W - m.r, y: height - 6, 'text-anchor': 'end', class: 'tick' });
    axis.textContent = xLabel;
    svg.append(axis);
    const yAxis = s('text', { x: m.l, y: m.t + 2, class: 'tick' });
    yAxis.textContent = unit;
    svg.append(yAxis);
    if (baseline !== null) {
      svg.append(s('line', { x1: m.l, x2: W - m.r, y1: Y(baseline.value), y2: Y(baseline.value), class: 'baseline' }));
      const label = s('text', { x: W - m.r - 4, y: Y(baseline.value) - 5, 'text-anchor': 'end', class: 'tick' });
      label.textContent = baseline.label;
      svg.append(label);
    }
    for (const d of series) {
      const path = d.y.map((v, i) => `${i ? 'L' : 'M'}${X(d.x[i]).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
      svg.append(s('path', { d: path, fill: 'none', stroke: d.color, 'stroke-width': 2, 'stroke-linejoin': 'round' }));
    }
    if (labelled) {
      // Lines often end close together, so push the end labels apart.
      const ends = series.map((d) => ({ name: d.name, y: Y(d.y[d.y.length - 1]) })).sort((p, q) => p.y - q.y);
      ends.forEach((e, i) => { if (i && e.y < ends[i - 1].y + 15) e.y = ends[i - 1].y + 15; });
      for (const e of ends) {
        const label = s('text', { x: W - m.r + 8, y: e.y + 4, class: 'tick' });
        label.textContent = e.name;
        svg.append(label);
      }
    }
    cross = s('line', { y1: m.t, y2: height - m.b, class: 'cross', visibility: 'hidden' });
    svg.append(cross);
    if (marked !== null) show(marked, false);
  }
  box.prepend(svg);
  draw();
  new ResizeObserver(([e]) => {
    const next = Math.round(e.contentRect.width);
    if (next > 0 && next !== W) { W = next; requestAnimationFrame(draw); }
  }).observe(box);

  function show(i, emit = true) {
    marked = i;
    if (i === null) {
      cross.setAttribute('visibility', 'hidden');
      tip.hidden = true;
      if (emit && onHover) onHover(null);
      return;
    }
    const px = X(xs[i]);
    cross.setAttribute('x1', px);
    cross.setAttribute('x2', px);
    cross.setAttribute('visibility', 'visible');
    tip.replaceChildren(
      h('strong', {}, `${xs[i]}${xUnit}`),
      ...series.map((d) => h('div', {}, h('span', { class: 'swatch', style: `background:${d.color}` }),
        `${series.length > 1 ? `${d.name}: ` : ''}${d.y[i]} ${unit}`)),
    );
    tip.hidden = false;
    tip.style.left = `${Math.min(70, (px / W) * 100)}%`;
    if (emit && onHover) onHover(i);
  }

  const pick = (ev) => {
    const r = svg.getBoundingClientRect();
    const vx = ((ev.clientX - r.left) / r.width) * W;
    let best = 0;
    xs.forEach((x, i) => { if (Math.abs(X(x) - vx) < Math.abs(X(xs[best]) - vx)) best = i; });
    show(best);
  };
  svg.addEventListener('pointermove', pick);
  svg.addEventListener('pointerdown', pick);
  svg.addEventListener('pointerleave', () => show(null));

  wrap.mark = (i) => show(i, false);
  return wrap;
}

// The same numbers as the lines, built on first open because most readers never ask for them.
const MAX_ROWS = 30;
function numbers({ title, unit, xLabel, xs, series }) {
  const more = h('details', { class: 'more' }, h('summary', {}, t('Show the numbers', 'Показати числа')));
  more.addEventListener('toggle', () => {
    if (!more.open || more.querySelector('table')) return;
    const step = Math.max(1, Math.ceil(xs.length / MAX_ROWS));
    const rows = [];
    for (let i = 0; i < xs.length; i += step) rows.push([xs[i], ...series.map((d) => d.y[i])]);
    const caption = step > 1
      ? t(`${title}, ${unit}. Every ${step}th sample.`, `${title}, ${unit}. Кожна ${step}-та точка.`)
      : `${title}, ${unit}`;
    more.append(h('div', { class: 'table-wrap' }, dataTable(caption, [xLabel, ...series.map((d) => d.name)], rows)));
  });
  return more;
}

export function dataTable(caption, headers, rows) {
  return h('table', { class: 'data' }, h('caption', {}, caption),
    h('thead', {}, h('tr', {}, headers.map((c) => h('th', { scope: 'col' }, c)))),
    h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c, i) => h('td', { 'data-label': headers[i] }, c))))));
}
