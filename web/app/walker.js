// Three.js walker. Every bone pose comes from the transforms of the muscle-driven
// OpenSim run served by /api/opensim_mesh; nothing is keyframed by hand.
import { getJSON, reducedMotion } from './ui.js';

let meshData = null;
export async function loadMesh() {
  if (!meshData) meshData = await getJSON('/api/opensim_mesh');
  return meshData;
}

const seg = (obj, a, b) => {
  const A = new THREE.Vector3(...a);
  const B = new THREE.Vector3(...b);
  const d = new THREE.Vector3().subVectors(B, A);
  const len = d.length() || 1e-6;
  obj.position.copy(A).add(B).multiplyScalar(0.5);
  obj.scale.set(1, len, 1);
  obj.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
};

export function createWalker(host, data, { height = 460, onFrame = null, orbit = true } = {}) {
  const width = () => host.clientWidth || 560;
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(36, width() / height, 0.01, 100);
  const ren = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  ren.setSize(width(), height);
  ren.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  host.append(ren.domElement);

  scene.add(new THREE.AmbientLight(0xc9d6d3, 0.62));
  const key = new THREE.DirectionalLight(0xfff1dc, 1.1);
  key.position.set(2, 3.5, 2.5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x7fc4b6, 0.7);
  rim.position.set(-2.5, 1.5, -2);
  scene.add(rim);

  // Floor lines slide under the figure so a walk in place reads as walking.
  const floor = new THREE.Group();
  const lineMat = new THREE.LineBasicMaterial({ color: 0x47555a });
  for (let i = -8; i <= 8; i += 1) {
    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(i * 0.25, 0, -1.6), new THREE.Vector3(i * 0.25, 0, 1.6),
    ]);
    floor.add(new THREE.Line(g, lineMat));
  }
  scene.add(floor);

  const root = new THREE.Group();
  scene.add(root);
  const bone = new THREE.MeshStandardMaterial({ color: 0xece9df, roughness: 0.58, metalness: 0.04 });
  const bodies = {};
  for (const b of data.bodies) {
    const md = data.meshes[b];
    if (!md) continue;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(md.verts, 3));
    g.setIndex(md.faces);
    g.computeVertexNormals();
    const mesh = new THREE.Mesh(g, bone);
    mesh.matrixAutoUpdate = false;
    root.add(mesh);
    bodies[b] = mesh;
  }

  // Translucent body envelope around the bones.
  const skin = new THREE.MeshStandardMaterial({
    color: 0x63a999, roughness: 0.7, transparent: true, opacity: 0.26, depthWrite: false,
  });
  const flesh = new THREE.Group();
  root.add(flesh);
  const limb = (ra, rb) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(rb, ra, 1, 18, 1), skin);
    flesh.add(m);
    return m;
  };
  const ball = (r) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 14), skin);
    flesh.add(m);
    return m;
  };
  const F = {
    torso: limb(0.19, 0.15), neck: limb(0.055, 0.05), head: ball(0.115), pelvis: ball(0.155),
    chest: ball(0.175), Lthigh: limb(0.115, 0.08), Lshank: limb(0.08, 0.05), Lfoot: limb(0.05, 0.038),
    Rthigh: limb(0.115, 0.08), Rshank: limb(0.08, 0.05), Rfoot: limb(0.05, 0.038),
  };

  const frames = data.transforms;
  const org = (f, b) => (f[b] ? [f[b][12], f[b][13], f[b][14]] : null);
  let index = 0;
  let playing = !reducedMotion();
  let raf = 0;
  let last = 0;
  let accum = 0;
  let theta = 0.75;
  const fps = 30;

  function pose(i) {
    const f = frames[i];
    for (const b of Object.keys(bodies)) if (f[b]) bodies[b].matrix.fromArray(f[b]);
    const pel = org(f, 'pelvis');
    const tor = org(f, 'torso');
    const sh = [tor[0], tor[1] + 0.06, tor[2]];
    const head = [tor[0], tor[1] + 0.3, tor[2]];
    seg(F.torso, pel, sh);
    F.pelvis.position.set(...pel);
    F.chest.position.set(pel[0] + (sh[0] - pel[0]) * 0.74, pel[1] + (sh[1] - pel[1]) * 0.74, pel[2] + (sh[2] - pel[2]) * 0.74);
    seg(F.neck, sh, [tor[0], tor[1] + 0.2, tor[2]]);
    F.head.position.set(...head);
    for (const [S, s] of [['L', 'l'], ['R', 'r']]) {
      const hip = org(f, `femur_${s}`);
      const knee = org(f, `tibia_${s}`);
      const heel = org(f, `calcn_${s}`);
      const toe = org(f, `toes_${s}`);
      seg(F[`${S}thigh`], hip, knee);
      seg(F[`${S}shank`], knee, heel);
      seg(F[`${S}foot`], heel, toe);
    }
    root.position.set(-pel[0], 0, -pel[2]);
    if (onFrame) onFrame(i);
  }

  function draw() {
    const r = 3.1;
    cam.position.set(Math.sin(theta) * r, 1.15, Math.cos(theta) * r);
    cam.lookAt(0, 0.86, 0);
    ren.render(scene, cam);
  }

  function loop(ts) {
    raf = requestAnimationFrame(loop);
    if (!playing) return;
    accum += ts - last;
    last = ts;
    if (accum < 1000 / fps) return;
    const stepFrames = Math.floor(accum / (1000 / fps));
    accum -= stepFrames * (1000 / fps);
    index = (index + stepFrames) % frames.length;
    pose(index);
    floor.position.x = -((index / frames.length) * 1.25 % 0.25);
    if (orbit) theta += 0.0012 * stepFrames;
    draw();
  }

  const onResize = () => {
    cam.aspect = width() / height;
    cam.updateProjectionMatrix();
    ren.setSize(width(), height);
    draw();
  };
  window.addEventListener('resize', onResize);

  pose(0);
  draw();
  last = performance.now();
  raf = requestAnimationFrame(loop);

  return {
    frameCount: frames.length,
    get playing() { return playing; },
    play() { playing = true; last = performance.now(); accum = 0; },
    pause() { playing = false; },
    seek(i) { index = i; pose(i); draw(); },
    destroy() {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      ren.dispose();
      ren.domElement.remove();
    },
  };
}

// Sagittal joint angles read back from the same transforms the figure is drawn with.
// Column-major 4x4; OpenSim's z axis is the flexion axis of the hip and knee.
function relativeZ(parent, child) {
  const col = (m, c) => [m[c * 4], m[c * 4 + 1], m[c * 4 + 2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const px = col(parent, 0);
  const py = col(parent, 1);
  const cx = col(child, 0);
  return (Math.atan2(dot(py, cx), dot(px, cx)) * 180) / Math.PI;
}

export function jointAngles(data) {
  return data.transforms.map((f) => ({
    hipR: relativeZ(f.pelvis, f.femur_r),
    hipL: relativeZ(f.pelvis, f.femur_l),
    kneeR: -relativeZ(f.femur_r, f.tibia_r),
    kneeL: -relativeZ(f.femur_l, f.tibia_l),
  }));
}
