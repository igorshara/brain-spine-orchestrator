import { h, t } from './ui.js';
import { createWalker, loadMesh } from './walker.js';

// Measured from tools/blender/system_scene.json, then nudged off the device so the mark does not cover it.
const PARTS = [
  { x: 84, y: 41, name: ['Controller', 'Пульт'], say: ['The screen in your hand. It knows only what the implant last told it.', 'Екран у вашій руці. Він знає лише те, що імплант сказав йому востаннє.'] },
  { x: 50, y: 55, name: ['Communicator', 'Комунікатор'], say: ['Worn on a belt, it carries each command across the radio link.', 'Носиться на поясі й передає кожну команду радіоканалом.'] },
  { x: 51, y: 67, name: ['Implant', 'Імплант'], say: ['It keeps doing what it last heard, whether or not the screen knows.', 'Робить те, що почув востаннє, незалежно від того, чи знає про це екран.'] },
  { x: 28.5, y: 47, name: ['Lead', 'Електрод'], say: ['It delivers the pulses at the spinal cord.', 'Подає імпульси до спинного мозку.'] },
];

const SOURCE = 'https://medicalxpress.com/news/2022-04-home-epidural-people-spinal-cord.html';

export function mount(root) {
  const stage = h('div', { class: 'stage-canvas', 'data-testid': 'walker' },
    h('p', { class: 'stage-wait', role: 'status' }, t('Loading the walking model', 'Завантажую модель ходи')));
  const label = h('p', { class: 'stage-label' }, t('Simulated movement, not a treatment result', 'Симульований рух, а не результат лікування'));
  let walker = null;
  let gone = false;

  root.replaceChildren(h('div', { class: 'overview' },
    h('section', { class: 'hero' },
      h('div', { class: 'hero-copy' },
        h('h1', {}, t('Forgetting a remote should not cost five days.', 'Забутий пульт не має коштувати п’яти днів.')),
        h('p', { class: 'lead' }, t('I live with an implanted spinal stimulator. Once I left the remote behind and waited five to six days for it. Another time I forgot to switch the stimulator off. It ran for a long time and strong spasms followed.',
          'Я живу з імплантованим спинальним стимулятором. Одного разу я забув пульт і чекав на нього п’ять-шість днів. Іншого разу забув вимкнути стимулятор. Він довго працював, а потім почались сильні спазми.')),
        h('p', {}, t('Here are both days as you can play them, and how a controller could have handled them.',
          'Тут обидва ці дні можна програти і побачити, як із ними міг би впоратись пульт.')),
        h('div', { class: 'hero-actions' },
          h('a', { class: 'btn btn-primary', href: '#controller/home' }, t('Play the forgotten remote', 'Програти забутий пульт')),
          h('a', { class: 'btn btn-primary', href: '#session/unanswered' }, t('Play the forgotten shutoff', 'Програти забуте вимкнення'))),
        h('p', { class: 'small' }, t('The link between the long run and the spasms is my own report and has not been measured.',
          'Зв’язок між довгою роботою і спазмами лише моє спостереження, його не вимірювали.'))),
      h('figure', { class: 'stage' }, stage, h('figcaption', {}, label))),
    h('section', { class: 'idea' },
      h('h2', {}, t('The idea in one picture', 'Ідея однією картинкою')),
      h('p', { class: 'lead' }, t('A controller knows only what the implant has told it. When the link drops, these two can disagree, and the screen should say so.',
        'Пульт знає лише те, що йому сказав імплант. Коли зв’язок зникає, ці двоє можуть розходитись, і екран має про це казати.')),
      h('div', { class: 'scene' },
        h('figure', { class: 'scene-fig' },
          h('div', { class: 'scene-img', 'data-testid': 'scene' },
            h('img', { src: '/app/system_scene.webp', width: 900, height: 1080, alt: t('A standing figure with a tablet controller in one hand, a communicator on a belt, an implant at the hip and a lead along the spine. Dotted radio paths join controller, communicator and implant.',
              'Людина стоїть із планшетним пультом у руці, комунікатор на поясі, імплант біля стегна й електрод уздовж хребта. Пунктирні радіошляхи з’єднують пульт, комунікатор та імплант.') }),
            PARTS.map((p, i) => h('span', { class: 'scene-mark', style: `left:${p.x}%;top:${p.y}%`, 'aria-hidden': 'true' }, i + 1))),
          h('figcaption', { class: 'small' }, t('Illustration. Generic devices, not to scale.', 'Ілюстрація. Узагальнені пристрої, не в масштабі.'))),
        h('ol', { class: 'scene-path' }, PARTS.map((p) => h('li', {},
          h('strong', {}, t(...p.name)), h('span', {}, t(...p.say)))))),
      h('div', { class: 'idea-grid' },
        h('div', { class: 'idea-cell' },
          h('p', { class: 'idea-case' }, t('The command was lost', 'Загубилась команда')),
          h('p', {}, t('Controller: ', 'Пульт: '), h('strong', { class: 'hatch' }, t('Unknown', 'Невідомо'))),
          h('p', {}, t('Implant: ', 'Імплант: '), h('strong', {}, t('still stimulating', 'досі стимулює')))),
        h('div', { class: 'idea-cell' },
          h('p', { class: 'idea-case' }, t('The answer was lost', 'Загубилась відповідь')),
          h('p', {}, t('Controller: ', 'Пульт: '), h('strong', { class: 'hatch' }, t('Unknown', 'Невідомо'))),
          h('p', {}, t('Implant: ', 'Імплант: '), h('strong', {}, t('stopped', 'зупинився'))))),
      h('p', {}, h('a', { href: '#controller/command' }, t('See it happen', 'Подивитись, як це відбувається')))),
    h('section', { class: 'two-col' },
      h('div', {},
        h('h2', {}, t('What this is', 'Що це')),
        h('ul', { class: 'plain' },
          h('li', {}, t('A simulator you can use in a browser.', 'Симулятор, яким можна користуватись у браузері.')),
          h('li', {}, t('A concept for how a patient’s controller could behave when things go wrong.', 'Концепція того, як пульт пацієнта міг би поводитись, коли щось іде не так.')),
          h('li', {}, t('My own stimulation programs, published by me, with simulated responses.', 'Мої власні програми стимуляції, опубліковані мною, із симульованими відповідями.')))),
      h('div', {},
        h('h2', {}, t('What this is not', 'Чим це не є')),
        h('ul', { class: 'plain' },
          h('li', {}, t('It connects to no implant, controller or telemetry.', 'Він не під’єднаний до імплантів, пультів чи телеметрії.')),
          h('li', {}, t('It is not a feature of any existing system.', 'Це не функція жодної наявної системи.')),
          h('li', {}, t('It does not show that any treatment works.', 'Він не показує, що якесь лікування працює.'))))),
    h('section', { class: 'context' },
      h('h2', {}, t('Why now', 'Чому зараз')),
      h('p', {}, t('By April 2022, researchers at the University of Louisville, working with Medtronic, the Kessler Foundation and Johns Hopkins APL, had given a tablet controller to 16 research participants. Limited hand function drove that work. The report does not mention forgotten controllers or forgotten shutoff, which is where this concept starts.',
        'До квітня 2022 року дослідники Луїсвільського університету разом із Medtronic, Kessler Foundation та Johns Hopkins APL передали планшетний пульт 16 учасникам дослідження. Причиною була обмежена функція рук. У повідомленні не згадано ні забутий пульт, ні забуте вимкнення, і саме з цього починається ця концепція.')),
      h('p', { class: 'small' }, h('a', { href: SOURCE, rel: 'noopener', target: '_blank' }, t('Source: Medical Xpress, April 2022', 'Джерело: Medical Xpress, квітень 2022'))))));

  loadMesh().then((data) => {
    if (gone) return;
    stage.replaceChildren();
    walker = createWalker(stage, data, { height: stage.clientHeight || 460 });
  }).catch(() => {
    stage.replaceChildren(h('p', { class: 'stage-error' }, t('The walking model did not load. Reload the page to try again.', 'Модель ходи не завантажилась. Оновіть сторінку.')));
  });

  return { destroy() { gone = true; walker?.destroy(); } };
}
