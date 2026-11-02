// Small DOM and language helpers shared by every screen.
let lang = 'en';
try { lang = localStorage.getItem('bso-lang') === 'uk' ? 'uk' : 'en'; } catch (e) { /* storage blocked */ }

export const getLang = () => lang;
export function setLang(next) {
  lang = next;
  try { localStorage.setItem('bso-lang', next); } catch (e) { /* storage blocked */ }
  document.documentElement.lang = next;
}
export const t = (en, uk) => (lang === 'uk' ? uk : en);

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const p = (n) => String(n).padStart(2, '0');
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`;
}

export function ago(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return t(`${s} s`, `${s} с`);
  if (s < 3600) return t(`${Math.round(s / 60)} min`, `${Math.round(s / 60)} хв`);
  const hours = Math.floor(s / 3600);
  const mins = Math.round((s % 3600) / 60);
  return t(`${hours} h ${mins} min`, `${hours} год ${mins} хв`);
}

// A program with a fixed value reads as one number, not as a range.
export const range = ([a, b]) => (a === b ? `${a}` : `${a}–${b}`);

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return res.json();
}
