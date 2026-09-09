/* =============================================================
   Лабіринт для двох — рушій.
   Тексти — у content.js. Тут тільки поведінка, анімація і звук.
   Цільовий пристрій: iPhone, Safari, портрет.
   ============================================================= */
(() => {
'use strict';

const C = window.CONTENT;
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const SVGNS = 'http://www.w3.org/2000/svg';

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const D = k => Math.round(k * (REDUCED ? 0.35 : 1));   // тривалості
const wait = ms => new Promise(r => setTimeout(r, ms));

/* ---------- Секрет ---------- *
 * Стать не лежить у коді відкрито: у content.js тільки `secretToken` —
 * відбиток пари (пін-код + стать). Правильний пін-код і відмикає двері,
 * і водночас розкриває, який із варіантів справжній.
 * `?s=` лишається чорним ходом для Ігоря — щоб прогнати сценарій без коду;
 * параметр стирається з адреси одразу, як і раніше.                        */
const OVERRIDE = (() => {
  let s = null;
  try {
    const v = new URLSearchParams(location.search).get('s');
    if (v && C.variants[v]) s = v;
  } catch (_) {}
  if (location.search) {
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (_) {}
  }
  return s;
})();

let SECRET = null;
let VARIANT = null;
const setSecret = k => { SECRET = k; VARIANT = C.variants[k]; };

const KEY_STORE = 'lab_k';       // пін-код, щоб перезавантаження не замикало двері
const SEEN_STORE = 'lab_seen';   // заставку вже читали
const WHO_STORE = 'lab_who';     // хто відкрив посилання: 'a' — Саша, 'b' — Софія

const ls = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} },
  del(k) { try { localStorage.removeItem(k); } catch (_) {} }
};

const checkPin = pin => window.LabHash.slow(String(pin)) === C.lock.pinHash;

/* Який із варіантів справжній — знає тільки пін-код.
   Якщо жоден не збігся (хтось наплутав із токеном) — беремо перший ключ,
   а не «правильний»: інакше відповідь лежала б у content.js відкритим текстом. */
function resolveSecret(pin) {
  const keys = Object.keys(C.variants);
  for (const k of keys) {
    if (window.LabHash.sha256hex('v|' + pin + '|' + k) === C.lock.secretToken) return k;
  }
  return keys[0];
}

/* =============================================================
   Анімаційний хелпер. Використовує GSAP, коли він доступний,
   інакше — власний rAF-цикл. Візуально шлях один і той самий.
   ============================================================= */
const easeInOutCubic = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;

function tween(ms, onUpdate, ease = 'power2.inOut') {
  const dur = D(ms);
  return new Promise(resolve => {
    if (dur <= 0) { onUpdate(1); resolve(); return; }
    const o = { p: 0 };
    if (window.gsap) {
      window.gsap.to(o, {
        p: 1, duration: dur / 1000, ease,
        onUpdate: () => onUpdate(o.p),
        onComplete: () => { onUpdate(1); resolve(); }
      });
      return;
    }
    const t0 = performance.now();
    const step = now => {
      const p = Math.min(1, (now - t0) / dur);
      onUpdate(easeInOutCubic(p));
      p < 1 ? requestAnimationFrame(step) : resolve();
    };
    requestAnimationFrame(step);
  });
}

/* =============================================================
   Екрани: єдиний стиль переходу — cross-fade + ледь помітний зсув.
   ============================================================= */
const screens = {};
$$('.screen').forEach(el => screens[el.dataset.screen] = el);
let current = null;

async function show(name) {
  if (current === name) return;
  const next = screens[name];
  const prev = current ? screens[current] : null;
  if (prev) {
    prev.classList.remove('is-on');
    await wait(D(320));
  }
  next.classList.add('is-on');
  current = name;
  await wait(D(300));
}

/* =============================================================
   Звук. Стартує тільки після першого тапу (обмеження iOS/Android).
   Якщо файлу немає — застосунок працює далі мовчки.
   ============================================================= */
const Audio_ = (() => {
  const els = { prologue: $('#aPrologue'), walk: $('#aWalk'),
                reveal: $('#aReveal'), memories: $('#aMemories') };
  const ok = { prologue: false, walk: false, reveal: false, memories: false };
  const target = { prologue: 0.5, walk: 0.34, reveal: 0.8, memories: 0.4 };   // стеля гучності
  let muted = ls.get('lab_muted') === '1';   // тільки через обгортку: пряме звернення кидає в приватній вкладці
  let unlocked = false;
  const btn = $('#soundToggle');

  Object.keys(els).forEach(k => {
    const src = C.audio[k];
    if (src) els[k].src = src;
    els[k].volume = 0;
    ok[k] = !!src;          // оптимістично: mp3 грає з потоку, не чекаючи повного файлу
  });

  function markReady(k) { ok[k] = true; }
  function markFailed(k) { ok[k] = false; }   // файлу немає або він битий — далі мовчки

  /* Розблокування в момент першого тапу. pause() — СИНХРОННО одразу після
     play(): якщо ставити його в .then(), проміс дорешується вже після того,
     як ми запустили walk, і глушить трек. */
  function unlock() {
    if (unlocked) return;
    unlocked = true;
    Object.values(els).forEach(a => {
      if (!a.src) return;
      a.volume = 0;
      const p = a.play();
      if (p && p.catch) p.catch(() => {});
      a.pause();
      a.currentTime = 0;
    });
  }

  async function fadeTo(k, to, ms) {
    const a = els[k];
    if (!ok[k] || !a.src) return;
    const from = a.volume;
    const cap = muted ? 0 : 1;
    await tween(ms, p => { a.volume = Math.max(0, Math.min(1, (from + (to - from) * p) * cap)); }, 'none');
  }

  async function play(k, ms = 1400, mult = 1) {
    const a = els[k];
    if (!ok[k] || !a.src || muted) return;
    if (a.paused) {                       // якщо трек уже грає — не зривати його на нуль
      a.volume = 0;
      try { await a.play(); } catch (_) { return; }
    }
    await fadeTo(k, target[k] * mult, ms);
  }

  async function stop(k, ms = 900) {
    const a = els[k];
    if (!ok[k] || !a.src) return;
    await fadeTo(k, 0, ms);
    a.pause();
  }

  /* Плавний підйом гучності — використовується під шкалу вердикту */
  function swell(k, mult, ms) { return fadeTo(k, target[k] * mult, ms); }

  function syncBtn() {
    btn.classList.toggle('is-muted', muted);
    btn.setAttribute('aria-label', muted ? 'Увімкнути звук' : 'Вимкнути звук');
  }
  /* Довге утримання (1,6 с) — потайний вхід до панелі ведучого.
     Випадково не спрацює, а Ігорю не треба дописувати #host в адресу. */
  let longPress = false, holdTimer = null;
  const hold = () => { holdTimer = setTimeout(() => { longPress = true; location.hash = '#host'; }, 1600); };
  const release = () => clearTimeout(holdTimer);
  btn.addEventListener('pointerdown', hold);
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(e => btn.addEventListener(e, release));

  btn.addEventListener('click', () => {
    if (longPress) { longPress = false; return; }   // це був вхід у панель, не перемикач
    muted = !muted;
    ls.set('lab_muted', muted ? '1' : '0');
    Object.keys(els).forEach(k => {
      if (muted) els[k].volume = 0;
      else if (!els[k].paused) els[k].volume = target[k];
    });
    syncBtn();
  });
  syncBtn();

  /* Повернення з фону: iOS ставить трек на паузу */
  document.addEventListener('visibilitychange', () => {
    if (document.hidden || muted) return;
    Object.keys(els).forEach(k => {
      const a = els[k];
      if (a.dataset.wanted === '1' && a.paused) a.play().catch(() => {});
    });
  });

  return { els, markReady, markFailed, unlock, play, stop, swell, reveal: () => els.reveal,
           get muted() { return muted; }, showBtn: () => btn.hidden = false };
})();

/* =============================================================
   Прелоад. Усе вантажиться на інтро-екрані; під час гри —
   жодного мережевого запиту.
   ============================================================= */
async function preload(onProgress) {
  const jobs = [];

  Object.keys(C.audio).forEach(k => {
    const src = C.audio[k];
    if (!src) return;
    jobs.push(new Promise(res => {
      const a = Audio_.els[k];
      let done = false;
      /* Прелоад лише ЧЕКАЄ. Мовчазним трек робить тільки справжня помилка
         завантаження: повільна мережа не має глушити музику назавжди. */
      const finish = () => { if (done) return; done = true; res(); };
      a.addEventListener('canplaythrough', () => { Audio_.markReady(k); finish(); }, { once: true });
      a.addEventListener('error', () => { Audio_.markFailed(k); finish(); }, { once: true });
      if (a.readyState >= 3) { Audio_.markReady(k); finish(); }
      setTimeout(finish, 9000);
      a.load();
    }));
  });

  photos.length = 0;
  (C.photos.items || []).forEach(item => {
    jobs.push(new Promise(res => {
      const img = new Image();
      img.decoding = 'async';
      img.onload  = () => { photos.push({ img, caption: item.caption || '', file: item.file }); res(); };
      img.onerror = () => res();
      img.src = 'assets/photos/' + item.file;
    }));
  });

  let done = 0;
  const total = Math.max(1, jobs.length);
  const tick = () => onProgress(++done / total);
  jobs.forEach(p => p.then(tick));
  await Promise.all(jobs);
  /* Порядок фото = порядок у content.js, а не порядок завантаження */
  const order = (C.photos.items || []).map(i => i.file);
  photos.sort((x, y) => order.indexOf(x.file) - order.indexOf(y.file));
  onProgress(1);
}
const photos = [];

/* =============================================================
   Лабіринт. Ліхтарики розставляються по реальній довжині кривої,
   фішка пливе саме вздовж неї (getPointAtLength), а не стрибком.
   ============================================================= */
const Maze = (() => {
  const paths = { a: $('#pathA'), b: $('#pathB') };
  const chips = { a: $('#chipA'), b: $('#chipB') };
  const groups = { a: $('#lanternsA'), b: $('#lanternsB') };
  const centre = $('#centre');
  const centreHalo = $('.centre-halo');
  const decor = $('#mazeDecor');
  const nodes = { a: [], b: [] };
  const lanterns = { a: [], b: [] };
  const lens = { a: 0, b: 0 };
  let steps = 0, totalSteps = 1;

  function pointAt(side, frac) {
    const p = paths[side].getPointAtLength(lens[side] * frac);
    return { x: p.x, y: p.y };
  }

  function build(perSide) {
    totalSteps = perSide * 2;
    ['a', 'b'].forEach(side => {
      const path = paths[side];
      lens[side] = path.getTotalLength();
      path.style.color = C.players[side].color;
      inkLayers(path, C.players[side].color);

      for (let i = 1; i <= perSide; i++) {
        const pt = pointAt(side, i / perSide);
        const halo = document.createElementNS(SVGNS, 'circle');
        halo.setAttribute('cx', pt.x); halo.setAttribute('cy', pt.y);
        halo.setAttribute('r', 9);
        halo.setAttribute('fill', C.players[side].color);
        halo.setAttribute('filter', 'url(#soft)');
        halo.setAttribute('class', 'lantern-halo');

        const dot = document.createElementNS(SVGNS, 'circle');
        dot.setAttribute('cx', pt.x); dot.setAttribute('cy', pt.y);
        dot.setAttribute('r', i === perSide ? 4 : 3.1);
        dot.setAttribute('class', 'lantern');
        dot.style.color = C.players[side].color;

        groups[side].append(dot, halo);
        lanterns[side].push({ dot, halo });
        nodes[side].push(pt);
      }

      const start = pointAt(side, 0);
      chips[side].style.color = C.players[side].color;
      chips[side].setAttribute('transform', `translate(${start.x} ${start.y})`);
    });
    buildDecor();
  }

  /* Товщина лінії «зі змінною»: кілька шарів однієї кривої з різною
     вагою і рваним пунктиром дають відчуття мальованої від руки карти. */
  function inkLayers(path, tint) {
    const d = path.getAttribute('d');
    const specs = [
      { w: 6.4, o: 0.10, dash: '',                  c: tint },   // тінь у кольорі гравця
      { w: 1.3, o: 0.34, dash: '26 7 44 11 17 8',   c: null },
      { w: 0.8, o: 0.22, dash: '9 21 33 13',        c: null }
    ];
    specs.forEach(sp => {
      const el = document.createElementNS(SVGNS, 'path');
      el.setAttribute('d', d);
      el.setAttribute('class', 'maze-ink');
      el.setAttribute('stroke', sp.c ? hexA(sp.c, sp.o) : 'rgba(233,199,102,' + sp.o + ')');
      el.setAttribute('stroke-width', sp.w);
      if (sp.dash) el.setAttribute('stroke-dasharray', sp.dash);
      path.parentNode.insertBefore(el, path);
    });
  }

  /* Тупикові відгалуження: декоративні, але живі — тихо мерехтять */
  function buildDecor() {
    const rnd = seed => { let s = seed; return () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648; };
    const r = rnd(20260908);
    ['a', 'b'].forEach(side => {
      for (let i = 0; i < 4; i++) {
        const at = 0.12 + i * 0.2 + r() * 0.07;
        const p0 = paths[side].getPointAtLength(lens[side] * at);
        const p1 = paths[side].getPointAtLength(lens[side] * at + 6);
        const nx = -(p1.y - p0.y), ny = (p1.x - p0.x);
        const n = Math.hypot(nx, ny) || 1;
        const dir = r() > 0.5 ? 1 : -1;
        const L = 22 + r() * 26;
        const ex = p0.x + (nx / n) * L * dir + (r() - .5) * 14;
        const ey = p0.y + (ny / n) * L * dir + (r() - .5) * 14;
        const cx = (p0.x + ex) / 2 + (r() - .5) * 20;
        const cy = (p0.y + ey) / 2 + (r() - .5) * 20;

        const br = document.createElementNS(SVGNS, 'path');
        br.setAttribute('d', `M ${p0.x.toFixed(1)} ${p0.y.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`);
        br.setAttribute('class', 'decor-branch');
        const sp = document.createElementNS(SVGNS, 'circle');
        sp.setAttribute('cx', ex.toFixed(1)); sp.setAttribute('cy', ey.toFixed(1));
        sp.setAttribute('r', 2.1);
        sp.setAttribute('class', 'decor-spark');
        if (!REDUCED) {
          const dur = (3.4 + r() * 3).toFixed(2), del = (r() * 4).toFixed(2);
          sp.style.animation = `flicker ${dur}s ease-in-out ${del}s infinite`;
          br.style.animation = `flicker ${(+dur + 1.6).toFixed(2)}s ease-in-out ${del}s infinite`;
        }
        decor.append(br, sp);
      }
    });
  }

  async function enter() {
    await tween(900, p => { chips.a.style.opacity = chips.b.style.opacity = p; }, 'power1.out');
  }

  /* Один крок: запалюємо наступний ліхтарик і ведемо фішку до нього */
  async function step(side, index, perSide) {
    const l = lanterns[side][index];
    l.dot.classList.add('is-lit');
    l.halo.style.opacity = '0.5';

    const from = index === 0 ? 0 : (index / perSide) * lens[side];
    const to = ((index + 1) / perSide) * lens[side];
    const chip = chips[side];

    await tween(1150, p => {
      const pt = paths[side].getPointAtLength(from + (to - from) * p);
      chip.setAttribute('transform', `translate(${pt.x.toFixed(2)} ${pt.y.toFixed(2)})`);
    }, 'power2.inOut');

    steps++;
    const glow = 0.18 + 0.82 * (steps / totalSteps);
    centreHalo.style.opacity = glow.toFixed(3);
    $('.centre-core').style.opacity = (0.5 + 0.5 * (steps / totalSteps)).toFixed(3);
    paths[side].classList.add('lit');
  }

  /* Фінал: обидві фішки зливаються в одну, центр розкривається */
  async function converge() {
    centre.classList.add('is-open');
    await tween(1000, p => {
      const s = 1 + p * 1.9;
      centreHalo.setAttribute('transform', `translate(${180 - 180 * s} ${180 - 180 * s}) scale(${s})`);
      chips.a.style.opacity = chips.b.style.opacity = String(1 - p * 0.75);
    }, 'power2.out');
  }

  return { build, enter, step, converge };
})();

/* =============================================================
   Конфеті
   ============================================================= */
const Confetti = (() => {
  const cv = $('#confetti');
  const ctx = cv.getContext('2d');
  let parts = [], raf = 0;

  function fit() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = innerWidth * dpr; cv.height = innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  addEventListener('resize', fit); fit();

  function burst(colors) {
    fit();
    const n = REDUCED ? 40 : 130;
    parts = Array.from({ length: n }, () => ({
      x: innerWidth * (0.15 + Math.random() * 0.7),
      y: -20 - Math.random() * innerHeight * 0.5,
      vx: (Math.random() - .5) * 1.6,
      vy: 1.4 + Math.random() * 2.4,
      w: 5 + Math.random() * 6, h: 8 + Math.random() * 8,
      rot: Math.random() * Math.PI, vr: (Math.random() - .5) * 0.14,
      c: colors[(Math.random() * colors.length) | 0],
      life: 1
    }));
    cancelAnimationFrame(raf);
    if (REDUCED) { draw(); return; }
    loop();
  }

  function draw() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    parts.forEach(p => {
      ctx.save();
      ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });
  }

  function loop() {
    let alive = false;
    parts.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.vy += 0.018; p.rot += p.vr;
      if (p.y > innerHeight * 0.84) p.life -= 0.02;
      if (p.life > 0 && p.y < innerHeight + 60) alive = true;
    });
    draw();
    if (alive) raf = requestAnimationFrame(loop);
    else ctx.clearRect(0, 0, innerWidth, innerHeight);
  }

  return { burst };
})();

/* =============================================================
   Фінальна картка → PNG для збереження в галерею
   ============================================================= */
function renderCard() {
  const W = 1080, H = 1350;
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  const x = cv.getContext('2d');

  const g = x.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#0d1322'); g.addColorStop(.55, '#080c17'); g.addColorStop(1, '#060911');
  x.fillStyle = g; x.fillRect(0, 0, W, H);

  const halo = x.createRadialGradient(W / 2, H * .46, 0, W / 2, H * .46, W * .62);
  halo.addColorStop(0, hexA(VARIANT.color, .30));
  halo.addColorStop(1, hexA(VARIANT.color, 0));
  x.fillStyle = halo; x.fillRect(0, 0, W, H);

  ribbon(x, W, 150, C.players.a.color);
  ribbon(x, W, H - 150, C.players.b.color);

  x.textAlign = 'center';
  x.fillStyle = 'rgba(200,189,169,.85)';
  x.font = '400 30px Georgia, serif';
  x.fillText(spaced(C.variants[SECRET].kicker.toUpperCase()), W / 2, H * .42);

  x.fillStyle = VARIANT.color;
  x.shadowColor = hexA(VARIANT.color, .55); x.shadowBlur = 60;
  x.font = '400 132px Georgia, serif';
  x.fillText(VARIANT.word, W / 2, H * .525);
  x.shadowBlur = 0;

  x.fillStyle = '#f3ecdd';
  x.font = '400 42px Georgia, serif';
  x.fillText(VARIANT.finalLine, W / 2, H * .615);

  x.fillStyle = 'rgba(200,189,169,.6)';
  x.font = '400 30px Georgia, serif';
  x.fillText(`${C.players.a.name} + ${C.players.b.name}`, W / 2, H * .685);

  return cv.toDataURL('image/png');
}
function ribbon(x, W, y, color) {
  const g = x.createLinearGradient(0, 0, W, 0);
  g.addColorStop(0, hexA(color, 0)); g.addColorStop(.5, hexA(color, .8)); g.addColorStop(1, hexA(color, 0));
  x.fillStyle = g; x.fillRect(0, y, W, 3);
}
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
const spaced = s => s.split('').join(' ');

/* =============================================================
   Сценарій
   ============================================================= */
const picked = [];

function fillStaticTexts() {
  $('#introTitle').textContent = C.intro.title;
  $('#introText').textContent = C.intro.text;
  $('#startBtn').textContent = C.intro.start;
  $('#handoffName').textContent = '';
  $('#verdictTitle').textContent = C.verdict.title;
  $('#scaleLabel').textContent = C.verdict.scaleLabel;
  $('#verdictNext').textContent = C.verdict.next;
  $('#revealLead').textContent = C.reveal.lead;
  $('#revealHint').textContent = C.reveal.hint;
  $('#revealNext').textContent = C.reveal.next;
  $('#photosTitle').textContent = C.photos.title;
  $('#prolHint').textContent = C.prologue.tapHint;
  $('#gateReplay').textContent = C.gate.replay;
  $('#saveBtn').textContent = C.final.save;
  $('.save-hint').textContent = C.final.saveHint;
}

/* --- Панель ведучого: чисте посилання + генератор нового коду --- */
function initHost() {
  const clean = location.origin + location.pathname;
  $('#hostLinkText').textContent = clean;

  $('#hostCopy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(clean); }
    catch (_) {
      const t = document.createElement('textarea');
      t.value = clean; document.body.append(t); t.select();
      try { document.execCommand('copy'); } catch (__) {}
      t.remove();
    }
    $('#hostCopied').hidden = false;
  });

  $$('.btn-host').forEach(b => b.addEventListener('click', () => {
    const pin = ($('#hostPin').value || '').replace(/\D/g, '');
    const out = $('#hostOut');
    if (pin.length < 4 || pin.length > 8) {
      out.textContent = 'Код має бути з 4–8 цифр.';
      out.hidden = false;
      return;
    }
    $$('.btn-host').forEach(o => o.style.opacity = o === b ? '1' : '.35');
    const secret = b.dataset.secret;
    out.textContent =
      'pinLength:   ' + pin.length + ',\n' +
      "pinHash:     '" + window.LabHash.slow(pin) + "',\n" +
      "secretToken: '" + window.LabHash.sha256hex('v|' + pin + '|' + secret) + "',";
    out.hidden = false;
  }));

  $('#hostCheck').addEventListener('click', () => {
    const pin = ($('#hostPin').value || '').replace(/\D/g, '');
    const out = $('#hostOut');
    if (!pin) { out.textContent = 'Введи код, який хочеш перевірити.'; out.hidden = false; return; }
    if (!checkPin(pin)) {
      out.textContent = 'Цей код НЕ відчиняє двері.';
    } else {
      const k = resolveSecret(pin);
      out.textContent = 'Код відчиняє двері.\nУ центрі буде: ' + C.variants[k].word + '.';
    }
    out.hidden = false;
  });

  $('#hostReset').addEventListener('click', () => {
    ls.del(KEY_STORE); ls.del(SEEN_STORE); ls.del(WHO_STORE);
    location.href = clean;
  });
}

/* =============================================================
   Заставка. Кожна сторінка — окремий екран; рядки проявляються
   один за одним, далі — по дотику будь-де.
   ============================================================= */
let prologueTapped = false;

/* Найперший дотик пари — і той, що проявляє рядки, і той, що гортає, —
   момент, коли браузер дозволяє звук. Далі музика заставки грає до «Увійти». */
function startPrologueAudio() {
  if (prologueTapped) return;
  prologueTapped = true;
  Audio_.unlock();
  Audio_.els.prologue.dataset.wanted = '1';
  Audio_.play('prologue', 4000);
}

function waitForTap(el) {
  return new Promise(resolve => {
    const on = () => { el.removeEventListener('click', on); resolve(); };
    el.addEventListener('click', on);
  });
}

/* Один обробник жестів на всю сторінку заставки.
   Свайп — це намір гортати, тож він гортає навіть під час проявлення рядків;
   тап під час проявлення — «покажи все одразу», тап на готовій — далі.
   Поріг 44 px і вимога, щоб рух був радше горизонтальним: інакше кожне
   здригання руки гортало б сторінку. */
function onGesture(el, cb) {
  const MIN = 44;
  let x0 = 0, y0 = 0, down = false;
  const onDown = e => { down = true; x0 = e.clientX; y0 = e.clientY; };
  const onCancel = () => { down = false; };
  const onUp = e => {
    if (!down) return;
    down = false;
    const dx = e.clientX - x0, dy = e.clientY - y0;
    const swipe = Math.abs(dx) >= MIN && Math.abs(dx) > Math.abs(dy);
    cb(swipe ? (dx < 0 ? 1 : -1) : 0);          // 1 — далі, -1 — назад, 0 — тап
  };
  el.addEventListener('pointerdown', onDown);
  el.addEventListener('pointerup', onUp);
  el.addEventListener('pointercancel', onCancel);
  return () => {
    el.removeEventListener('pointerdown', onDown);
    el.removeEventListener('pointerup', onUp);
    el.removeEventListener('pointercancel', onCancel);
  };
}

/* Хто відкрив посилання. Перший дотик пари — тут, тож саме звідси
   починається музика заставки. Вибір запам'ятовується на цьому телефоні. */
async function runWho() {
  const saved = ls.get(WHO_STORE);
  if (saved === 'a' || saved === 'b') return saved;

  $('#whoLead').textContent = C.who.lead;
  $('#whoSub').textContent = C.who.sub;

  const btns = { a: $('#whoA'), b: $('#whoB') };
  Object.keys(btns).forEach(k => {
    btns[k].textContent = C.players[k].name;
    btns[k].style.setProperty('--tone', C.players[k].color);
    btns[k].classList.remove('is-in', 'is-picked', 'is-dim');
  });

  await show('who');
  Object.keys(btns).forEach((k, i) => setTimeout(() => btns[k].classList.add('is-in'), D(320 + i * 160)));

  const pick = await new Promise(resolve => {
    Object.keys(btns).forEach(k => btns[k].addEventListener('click', () => {
      startPrologueAudio();                     // дотик пари — момент, коли можна вмикати звук
      btns[k].classList.add('is-picked');
      btns[k === 'a' ? 'b' : 'a'].classList.add('is-dim');
      resolve(k);
    }, { once: true }));
  });

  ls.set(WHO_STORE, pick);
  await wait(D(760));
  return pick;
}

/* Заставка починається зі звертання до того, хто відкрив: сторінки з
   `tone` міняються місцями, решта лишається як є. Нічого не викидаємо. */
function pagesFor(who) {
  const pages = C.prologue.pages.slice();
  const slots = pages.map((pg, i) => (pg.tone === 'a' || pg.tone === 'b') ? i : -1).filter(i => i >= 0);
  if (slots.length < 2) return pages;
  const personal = slots.map(i => pages[i]);
  personal.sort((x, y) => (x.tone === who ? 0 : 1) - (y.tone === who ? 0 : 1));
  slots.forEach((slot, n) => { pages[slot] = personal[n]; });
  return pages;
}

async function runPrologue(who) {
  const screen = screens.prologue;
  const box = $('#prolLines'), hint = $('#prolHint'), dots = $('#prolDots');
  const pages = pagesFor(who);

  dots.innerHTML = '';
  pages.forEach(() => dots.append(document.createElement('i')));

  await show('prologue');

  for (let i = 0; i < pages.length; ) {
    const page = pages[i];
    const tone = page.tone ? C.players[page.tone].color : '';
    screen.querySelector('.screen-inner').style.setProperty('--tone', tone || 'var(--brass-lit)');
    [...dots.children].forEach((d, j) => d.classList.toggle('is-on', j === i));

    box.innerHTML = '';
    hint.classList.remove('is-in');
    hint.textContent = C.prologue.tapHint;

    const lines = page.lines.map((text, j) => {
      const el = document.createElement('p');
      el.className = 'prol-line' + (j === 0 && page.tone ? ' is-lead' : '');
      el.textContent = text;
      box.append(el);
      return el;
    });

    let skip = false, shown = false, resolveNav = null;
    const nav = new Promise(r => { resolveNav = r; });

    const detach = onGesture(screen, g => {
      startPrologueAudio();
      if (g === -1 && i === 0) return;                       // назад із першої нікуди — не переграємо її
      if (g !== 0) { skip = true; resolveNav(g); return; }   // свайп гортає одразу
      if (!shown) { skip = true; return; }                   // тап під час проявлення — показати все
      resolveNav(1);                                         // тап на готовій сторінці — далі
    });

    for (const el of lines) {
      if (!skip) await wait(D(560));
      el.classList.add('is-in');
    }
    if (!skip) await wait(D(900));
    hint.classList.add('is-in');
    shown = true;

    const dir = await nav;
    detach();

    const next = Math.max(0, i + dir);
    if (next !== i && next < pages.length) {
      lines.forEach(el => el.classList.remove('is-in'));
      hint.classList.remove('is-in');
      await wait(D(620));
    }
    i = next;
  }
  ls.set(SEEN_STORE, '1');
}

/* =============================================================
   Замок. Свій набірний пульт — щоб не смикати клавіатуру iOS
   і не ламати верстку.
   ============================================================= */
function buildKeypad() {
  const pad = $('#keypad');
  if (pad.children.length) return;
  const keys = ['1','2','3','4','5','6','7','8','9','', '0','⌫'];
  keys.forEach(k => {
    const b = document.createElement('button');
    b.type = 'button';
    if (k === '') { b.className = 'key key-blank'; b.disabled = true; }
    else if (k === '⌫') { b.className = 'key key-wipe'; b.textContent = k; b.dataset.key = 'del'; }
    else { b.className = 'key'; b.textContent = k; b.dataset.key = k; }
    pad.append(b);
  });
}

async function runGate() {
  for (;;) {
    const r = await gateOnce();
    if (r === 'replay') { await runPrologue(ls.get(WHO_STORE) || 'a'); continue; }
    return r;
  }
}

function gateOnce() {
  const box = $('#gateLines'), ask = $('#gateAsk'), cells = $('#pinCells');
  const msg = $('#pinMsg'), pad = $('#keypad'), replay = $('#gateReplay');
  const gate = screens.gate.querySelector('.gate');
  const N = C.lock.pinLength;

  gate.classList.remove('is-open');
  pad.classList.remove('is-locked');
  msg.classList.remove('is-in');
  buildKeypad();

  box.innerHTML = '';
  const lines = C.gate.lines.map(t => {
    const el = document.createElement('p');
    el.className = 'gate-line';
    el.textContent = t;
    box.append(el);
    return el;
  });
  ask.textContent = C.gate.ask;
  ask.classList.remove('is-in');
  replay.textContent = C.gate.replay;

  cells.innerHTML = '';
  const dots = Array.from({ length: N }, () => {
    const d = document.createElement('i');
    d.className = 'pin-cell';
    cells.append(d);
    return d;
  });
  pad.classList.remove('is-in');

  let pin = '';
  const paint = () => dots.forEach((d, i) => d.classList.toggle('is-set', i < pin.length));

  return new Promise(async resolve => {
    let done = false;
    const finish = v => { if (done) return; done = true; cleanup(); resolve(v); };

    const onKey = async e => {
      const k = e.target.dataset && e.target.dataset.key;
      if (!k || done) return;
      msg.classList.remove('is-in');
      if (k === 'del') { pin = pin.slice(0, -1); paint(); return; }
      if (pin.length >= N) return;
      pin += k;
      paint();
      if (pin.length === N) await verify();
    };

    const onReplay = () => finish('replay');

    function cleanup() {
      pad.removeEventListener('click', onKey);
      replay.removeEventListener('click', onReplay);
    }

    async function verify() {
      pad.classList.add('is-locked');
      msg.textContent = C.gate.unlocking;
      msg.classList.add('is-in');
      await wait(D(420));
      await new Promise(r => requestAnimationFrame(() => r()));   // дати екрану промалюватись

      const attempt = pin;
      if (!checkPin(attempt)) {
        cells.classList.add('is-wrong');
        msg.textContent = C.gate.wrong;
        await wait(D(560));
        cells.classList.remove('is-wrong');
        pin = ''; paint();
        pad.classList.remove('is-locked');
        return;
      }

      msg.classList.remove('is-in');
      gate.classList.add('is-open');
      for (const d of dots) { d.classList.add('is-ok'); await wait(D(90)); }
      await wait(D(900));
      finish(attempt);
    }

    pad.addEventListener('click', onKey);
    replay.addEventListener('click', onReplay);

    await show('gate');
    for (const el of lines) { await wait(D(620)); el.classList.add('is-in'); }
    await wait(D(700));
    ask.classList.add('is-in');
    await wait(D(500));
    pad.classList.add('is-in');
  });
}

/* --- Гра --- */
async function runGame() {
  const qs = C.questions;
  const perSide = { a: qs.filter(q => q.for === 'a').length, b: qs.filter(q => q.for === 'b').length };
  const idx = { a: 0, b: 0 };
  Maze.build(Math.max(perSide.a, perSide.b));

  await show('game');
  await Maze.enter();

  for (let i = 0; i < qs.length; i++) {
    const q = qs[i];
    const player = C.players[q.for];

    await showHandoff(player);
    await show('game');
    const answer = await askQuestion(q, player);
    picked.push({ trait: answer.trait, side: q.for });
    await Maze.step(q.for, idx[q.for]++, Math.max(perSide.a, perSide.b));
    await wait(D(320));
  }

  await Maze.converge();
  await wait(D(700));
}

async function showHandoff(player) {
  $('#handoffName').textContent = player.dative;
  $('#handoffName').style.color = player.color;
  $('#handoffDot').style.color = player.color;
  $('#handoffDot').style.background = player.color;
  $('.handoff-lead').textContent = C.handoff.lead;
  await show('handoff');
  await wait(D(1200));
}

function askQuestion(q, player) {
  const who = $('#qWho'), text = $('#qText'), box = $('#qAnswers');
  who.textContent = player.name;
  who.style.color = player.color;
  text.textContent = q.q;
  box.className = 'q-answers';
  box.innerHTML = '';

  const btns = q.answers.map(a => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'answer';
    b.textContent = a.text;
    b.style.color = player.color;
    box.append(b);
    return b;
  });

  /* Відповіді з'являються з невеликою затримкою одна за одною */
  btns.forEach((b, i) => setTimeout(() => b.classList.add('is-in'), D(220 + i * 130)));

  return new Promise(resolve => {
    btns.forEach((b, i) => b.addEventListener('click', async () => {
      box.classList.add('is-locked');
      b.classList.add('is-picked');
      btns.forEach(o => { if (o !== b) o.classList.add('is-dim'); });
      await wait(D(620));
      resolve(q.answers[i]);
    }, { once: true }));
  });
}

/* --- Вердикт: шкала росте синхронно зі звуком, портрет — рядок за рядком --- */
async function runVerdict() {
  const list = $('#portrait');
  list.innerHTML = '';
  const lead = document.createElement('li');
  lead.className = 'portrait-lead';
  lead.textContent = C.verdict.portraitLead;
  list.append(lead);

  const seen = new Set();
  const lines = [];
  picked.forEach(a => { if (a && a.trait && !seen.has(a.trait)) { seen.add(a.trait); lines.push(a); } });
  const items = lines.map(({ trait, side }) => {
    const li = document.createElement('li');
    li.textContent = trait;
    li.style.setProperty('--dot', C.players[side].color);   // хто це сказав
    list.append(li);
    return li;
  });

  $('#scaleFill').style.width = '0%';
  $('#verdictNext').hidden = true;
  await show('verdict');

  Audio_.swell('walk', 1.6, 2600);
  await tween(2600, p => { $('#scaleFill').style.width = (p * 100).toFixed(1) + '%'; }, 'power1.inOut');
  Audio_.swell('walk', 1, 1200);

  await wait(D(320));
  lead.classList.add('is-in');
  for (const li of items) { await wait(D(260)); li.classList.add('is-in'); }

  await wait(D(500));
  $('#verdictNext').hidden = false;
  await new Promise(r => $('#verdictNext').addEventListener('click', r, { once: true }));
}

/* --- Reveal --- */
async function runReveal() {
  $('#revealBefore').hidden = false;
  $('#revealAfter').hidden = true;
  $('#revealNext').hidden = true;
  $('#revealNext').classList.remove('is-in');
  await show('reveal');

  await new Promise(r => $('#heartBtn').addEventListener('click', r, { once: true }));

  const flash = $('#flash');
  flash.style.background = '#000';

  /* 1. Темрява і тиша */
  Audio_.stop('walk', 420);
  Audio_.els.walk.dataset.wanted = '0';
  await tween(450, p => { flash.style.opacity = String(p); }, 'power2.in');

  $('#revealBefore').hidden = true;
  $('#revealAfter').hidden = false;
  document.documentElement.style.setProperty('--reveal', VARIANT.color);
  document.documentElement.style.setProperty('--reveal-2', VARIANT.color2);
  $('#revealKicker').textContent = VARIANT.kicker;
  $('#revealWord').textContent = VARIANT.word;
  $('#revealSub').textContent = VARIANT.sub;
  const kicker = $('#revealKicker'), word = $('#revealWord'), sub = $('#revealSub');
  kicker.style.opacity = word.style.opacity = sub.style.opacity = '0';
  word.style.transform = 'scale(.94)';

  /* 2. Рівно секунда тиші й темряви. Це головний важіль — не скорочувати. */
  await wait(1000);

  /* 3. Спалах — і в цю ж мить стартує музика */
  flash.style.background = '#fff';
  Audio_.els.reveal.dataset.wanted = '1';
  Audio_.play('reveal', 200);
  Audio_.els.memories.dataset.wanted = '0';

  tween(900, p => { flash.style.opacity = String(1 - p); }, 'power2.out');

  await wait(D(180));
  tween(700, p => { kicker.style.opacity = String(p); }, 'power1.out');
  await wait(D(320));
  tween(900, p => {
    word.style.opacity = String(p);
    word.style.transform = `scale(${(0.94 + 0.06 * p).toFixed(3)})`;
  }, 'power2.out');
  Confetti.burst([VARIANT.color, VARIANT.color2, '#e9c766', '#f3ecdd']);
  await wait(D(700));
  tween(800, p => { sub.style.opacity = String(p); }, 'power1.out');

  await wait(D(2600));
  $('#revealNext').hidden = false;
  requestAnimationFrame(() => $('#revealNext').classList.add('is-in'));
  await new Promise(r => $('#revealNext').addEventListener('click', r, { once: true }));
}

/* --- Фото: Ken Burns + cross-fade --- */
async function runPhotos() {
  if (!photos.length) return;
  const stage = $('#photoStage');
  const cap = $('#photoCaption');
  stage.innerHTML = '';

  await Audio_.stop('reveal', 1200);
  Audio_.els.reveal.dataset.wanted = '0';
  Audio_.els.memories.dataset.wanted = '1';
  Audio_.play('memories', 1600);

  await show('photos');

  let skipped = false;
  const skip = new Promise(r => $('#photosSkip').addEventListener('click', () => { skipped = true; r(); }, { once: true }));

  const HOLD = REDUCED ? 2600 : 4600;
  for (let i = 0; i < photos.length && !skipped; i++) {
    const { img, caption } = photos[i];
    const el = img.cloneNode();
    el.className = '';
    stage.append(el);

    if (!REDUCED) {
      const dir = i % 2 ? -1 : 1;
      el.style.transform = `scale(1.06) translate(${dir * 1.5}%, ${-dir * 1.2}%)`;
      el.style.transition = `opacity 1.5s var(--ease), transform ${(HOLD + 1600) / 1000}s linear`;
      requestAnimationFrame(() => {
        el.classList.add('is-on');
        el.style.transform = `scale(1.16) translate(${-dir * 1.5}%, ${dir * 1.2}%)`;
      });
    } else {
      requestAnimationFrame(() => el.classList.add('is-on'));
    }

    cap.classList.remove('is-on');
    setTimeout(() => { cap.textContent = caption; if (caption) cap.classList.add('is-on'); }, D(700));

    await Promise.race([wait(HOLD), skip]);

    const prev = stage.children[0];
    if (prev && prev !== el) { prev.classList.remove('is-on'); setTimeout(() => prev.remove(), 1700); }
  }
  cap.classList.remove('is-on');
}

/* --- Фінальний кадр --- */
async function runFinal() {
  $('#finalKicker').textContent = VARIANT.kicker;
  $('#finalWord').textContent = VARIANT.word;
  $('#finalLine').textContent = VARIANT.finalLine;
  $('#photosSkip').hidden = true;
  await show('final');

  $('#saveBtn').addEventListener('click', () => {
    try {
      $('#saveImg').src = renderCard();
      $('#saveOverlay').hidden = false;
    } catch (_) {}
  });
  $('#saveClose').addEventListener('click', () => $('#saveOverlay').hidden = true);
}

/* =============================================================
   Старт
   ============================================================= */
async function main() {
  fillStaticTexts();

  /* Панель ведучого живе за #host — у посиланні для пари її немає */
  if (location.hash === '#host') { initHost(); await show('host'); return; }

  Audio_.showBtn();

  /* Ассети вантажаться фоном, поки читається заставка */
  const fill = $('#preloadFill');
  const preloading = preload(p => { fill.style.width = (p * 100).toFixed(0) + '%'; });

  let key = OVERRIDE;

  if (!key) {
    const saved = ls.get(KEY_STORE);          // двері вже відчиняли на цьому телефоні
    if (saved && checkPin(saved)) key = resolveSecret(saved);
  }

  if (!key) {
    if (!ls.get(SEEN_STORE)) await runPrologue(await runWho());
    const pin = await runGate();
    ls.set(KEY_STORE, pin);
    key = resolveSecret(pin);
  }

  setSecret(key);

  await show('intro');
  await preloading;
  $('#preload').classList.add('is-done');
  $('#startBtn').disabled = false;

  await new Promise(r => $('#startBtn').addEventListener('click', r, { once: true }));
  Audio_.unlock();
  Audio_.els.prologue.dataset.wanted = '0';
  Audio_.stop('prologue', 2200);            // перехресно: одна стихає, друга заходить
  Audio_.els.walk.dataset.wanted = '1';
  Audio_.play('walk', 2200);

  await runGame();
  await runVerdict();
  await runReveal();
  await runPhotos();
  await runFinal();
}

/* Зміна лише хеша не перезавантажує сторінку — тож робимо це самі,
   інакше додати #host на відкритій вкладці не спрацює. */
addEventListener('hashchange', () => {
  if ((location.hash === '#host') !== (current === 'host')) location.reload();
});

document.addEventListener('DOMContentLoaded', () => { main().catch(() => {}); });
})();
