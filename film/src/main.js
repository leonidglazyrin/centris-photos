import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { Pass, FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { buildTileArray, T, packSheet } from './textures.js';
import { generateWorld, meshVoxels, W, D, WATER_Y, Voxels, B } from './world.js';
import { createMaterials, createWaterMaterial, U } from './materials.js';
import { createSky } from './sky.js';
import { Character } from './characters.js';
import { Lantern, LightPool, buildBoat, buildMap, Particles, SkyLanterns, createMist } from './props.js';
import { FILM, needsLocalizedFrame } from './film.js';

const params = new URLSearchParams(location.search);
const OUT_W = +(params.get('w') ?? 1920), OUT_H = Math.round(OUT_W * 9 / 16);
const GL_W = OUT_W, GL_H = Math.round(OUT_W / 2.39);
const FPS = 24;

// ---------- fonts ----------
async function loadFonts() {
  const f = [
    ['Cormorant', 'node_modules/@fontsource/cormorant-garamond/files/cormorant-garamond-latin-600-normal.woff2', { weight: '600' }],
    ['Cormorant', 'node_modules/@fontsource/cormorant-garamond/files/cormorant-garamond-latin-400-italic.woff2', { weight: '400', style: 'italic' }],
    ['Cormorant', 'node_modules/@fontsource/cormorant-garamond/files/cormorant-garamond-latin-700-normal.woff2', { weight: '700' }],
    ['Nunito', 'node_modules/@fontsource/nunito/files/nunito-latin-600-normal.woff2', { weight: '600' }],
  ];
  for (const [fam, url, desc] of f) { const ff = new FontFace(fam, `url(${url})`, desc); await ff.load(); document.fonts.add(ff); }
}

// ---------- renderer ----------
const glCanvas = document.createElement('canvas');
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(GL_W, GL_H, false);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const out = document.createElement('canvas');
out.width = OUT_W; out.height = OUT_H;
document.body.appendChild(out);
const ctx2d = out.getContext('2d');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, GL_W / GL_H, 0.1, 1200);

// ---------- world ----------
const tileTex = buildTileArray();
U.uSnowTile.value = T.snow;
const mats = createMaterials(tileTex);
const world = generateWorld();
const CH = 32;
for (let cz = 0; cz < D; cz += CH) for (let cx = 0; cx < W; cx += CH) {
  const { opaque, cutout } = meshVoxels(world.V, cx, cz, Math.min(W, cx + CH), Math.min(D, cz + CH));
  if (opaque) { const m = new THREE.Mesh(opaque, mats.opaque); m.castShadow = m.receiveShadow = true; scene.add(m); }
  if (cutout) { const m = new THREE.Mesh(cutout, mats.cutout); m.castShadow = m.receiveShadow = true; m.customDepthMaterial = mats.depthCut; scene.add(m); }
}
// water: one big plane at the surface, with a planar reflection rendered each frame
const reflRT = new THREE.WebGLRenderTarget(Math.round(GL_W / 2), Math.round(GL_H / 2), { type: THREE.HalfFloatType });
U.tReflect.value = reflRT.texture;
const reflCam = new THREE.PerspectiveCamera();
const reflClip = [new THREE.Plane(new THREE.Vector3(0, 1, 0), -(WATER_Y - 0.1))];
const texBias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
function renderReflection() {
  camera.updateMatrixWorld();
  const dir = new THREE.Vector3(); camera.getWorldDirection(dir);
  reflCam.copy(camera);
  reflCam.position.set(camera.position.x, 2 * WATER_Y - camera.position.y, camera.position.z);
  reflCam.up.set(camera.up.x, -camera.up.y, camera.up.z);
  reflCam.lookAt(reflCam.position.clone().add(new THREE.Vector3(dir.x, -dir.y, dir.z)));
  reflCam.updateMatrixWorld(); reflCam.updateProjectionMatrix();
  U.uTexMat.value.copy(texBias).multiply(reflCam.projectionMatrix).multiply(reflCam.matrixWorldInverse);
  const hidden = [water, ...mistLayers()];
  const vis = hidden.map((o) => o.visible);
  hidden.forEach((o) => { o.visible = false; });
  renderer.clippingPlanes = reflClip;
  renderer.setRenderTarget(reflRT);
  renderer.render(scene, reflCam);
  renderer.setRenderTarget(null);
  renderer.clippingPlanes = [];
  hidden.forEach((o, i) => { o.visible = vis[i]; });
}
const mistLayers = () => scene.children.filter((o) => o.renderOrder === 5);
const water = new THREE.Mesh(new THREE.PlaneGeometry(600, 600, 1, 1), createWaterMaterial());
water.rotation.x = -Math.PI / 2; water.position.set(88, WATER_Y - 0.08, 98); water.receiveShadow = true; water.renderOrder = 2;
scene.add(water);

// Small voxel models for the sapling and its grown-up version on the hill
function voxelProp(fill, size = 9) {
  const V = new Voxels(size, 10, size);
  fill(V);
  const { opaque, cutout } = meshVoxels(V, 0, 0, size, size, 0, 10);
  const g = new THREE.Group();
  if (opaque) { const m = new THREE.Mesh(opaque, mats.opaque); m.castShadow = m.receiveShadow = true; g.add(m); }
  if (cutout) { const m = new THREE.Mesh(cutout, mats.cutout); m.castShadow = m.receiveShadow = true; m.customDepthMaterial = mats.depthCut; g.add(m); }
  return g;
}
const HILLTOP = new THREE.Vector3(142, world.topAt(142, 66) + 1, 66);
const sapling = voxelProp((V) => V.set(4, 0, 4, B.sapling));
sapling.position.set(HILLTOP.x - 4, HILLTOP.y, HILLTOP.z - 4);
const youngTree = voxelProp((V) => { let s = 1; const r = () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; world.cherryAt(4, 4, r, V, 0); });
youngTree.position.copy(sapling.position);
youngTree.scale.setScalar(1);
scene.add(sapling, youngTree);

// ---------- cast & props ----------
const juno = new Character('juno');
const rowan = new Character('rowan');
scene.add(juno.root, rowan.root);
const lanterns = world.lanternPosts.map((p) => { const l = new Lantern(); l.group.position.set(p[0], p[1], p[2]); scene.add(l.group); return l; });
const lastLantern = new Lantern(); lastLantern.group.position.set(...world.lastPost); scene.add(lastLantern.group);
const handLantern = new Lantern();
const workLantern = new Lantern(); workLantern.group.position.set(82.5, 23, 61.5); scene.add(workLantern.group);
const shelfLanterns = [[81.5, 23, 60.5], [84.5, 23, 60.5]].map((p) => { const l = new Lantern(); l.group.position.set(...p); scene.add(l.group); return l; });
const potato = new Lantern(); potato.group.scale.set(1.15, 0.8, 1.2); potato.group.rotation.z = 0.2;
const boat = buildBoat(mats); scene.add(boat.group);
const mapUnfinished = buildMap(false), mapFinished = buildMap(true);
const sketch = buildMap(false); sketch.scale.setScalar(0.55);
const lightPool = new LightPool(scene, 4);
const allLanterns = [...lanterns, lastLantern, handLantern, workLantern, ...shelfLanterns, potato, boat.lantern];

const sky = createSky(scene);
const mist = createMist(scene);
const fx = {
  petals: new Particles(scene, 900, 'square'),
  snow: new Particles(scene, 2600, 'square'),
  fireflies: new Particles(scene, 140, 'glow', { additive: true }),
  hearts: new Particles(scene, 10, 'heart'),
  smoke: new Particles(scene, 120, 'soft'),
  skyLanterns: new SkyLanterns(scene, 80),
};
Object.values(fx).forEach((p) => { if (p.uniforms) p.uniforms.uScale.value = GL_H * 1.2; });

// ---------- post ----------
const rtOpts = { type: THREE.HalfFloatType, samples: 4 };
const rt = new THREE.WebGLRenderTarget(GL_W, GL_H, rtOpts);
rt.depthTexture = new THREE.DepthTexture(GL_W, GL_H);
const composer = new EffectComposer(renderer, rt);
composer.setPixelRatio(1);
composer.setSize(GL_W, GL_H);
composer.renderTarget1.depthTexture = new THREE.DepthTexture(GL_W, GL_H);
composer.renderTarget2.depthTexture = new THREE.DepthTexture(GL_W, GL_H);
composer.addPass(new RenderPass(scene, camera));

class DofPass extends Pass {
  constructor() {
    super();
    this.uniforms = { tColor: { value: null }, tDepth: { value: null }, uFocus: { value: 10 }, uAperture: { value: 0 }, uNear: { value: 0.1 }, uFar: { value: 1200 }, uRes: { value: new THREE.Vector2(GL_W, GL_H) }, uMaxBlur: { value: 10 } };
    this.quad = new FullScreenQuad(new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy,0.0,1.0); }',
      fragmentShader: `
        uniform sampler2D tColor, tDepth; uniform float uFocus, uAperture, uNear, uFar, uMaxBlur; uniform vec2 uRes; varying vec2 vUv;
        float lin(float d){ float z = d*2.0-1.0; return 2.0*uNear*uFar/(uFar+uNear - z*(uFar-uNear)); }
        float coc(float z){ return clamp(abs(z - uFocus)/z * uAperture, 0.0, uMaxBlur); }
        void main(){
          float z = lin(texture2D(tDepth, vUv).x);
          float c0 = coc(z);
          vec3 acc = texture2D(tColor, vUv).rgb; float wsum = 1.0;
          const float GA = 2.39996323;
          for (int i = 1; i < 28; i++) {
            float r = sqrt(float(i)/28.0) * uMaxBlur;
            vec2 off = vec2(cos(float(i)*GA), sin(float(i)*GA)) * r / uRes;
            float zs = lin(texture2D(tDepth, vUv + off).x);
            float cs = coc(zs);
            float w = smoothstep(r - 1.0, r + 1.0, (zs < z ? cs : min(cs, c0)) );
            vec3 s = texture2D(tColor, vUv + off).rgb;
            acc += s * w; wsum += w;
          }
          gl_FragColor = vec4(acc/wsum, 1.0);
        }`,
    }));
  }
  render(renderer, writeBuffer, readBuffer) {
    this.uniforms.tColor.value = readBuffer.texture;
    this.uniforms.tDepth.value = readBuffer.depthTexture;
    this.uniforms.uNear.value = camera.near; this.uniforms.uFar.value = camera.far;
    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    this.quad.render(renderer);
  }
}
const dof = new DofPass();
composer.addPass(dof);
const bloom = new UnrealBloomPass(new THREE.Vector2(GL_W / 2, GL_H / 2), 0.5, 0.65, 0.9);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const grade = new ShaderPass({
  uniforms: {
    tDiffuse: { value: null }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(GL_W, GL_H) },
    uLift: { value: new THREE.Vector3(0.02, 0.012, 0.03) }, uGain: { value: new THREE.Vector3(1.03, 1.0, 0.95) }, uSat: { value: 1.08 },
    uVig: { value: 0.35 }, uGrain: { value: 0.02 }, uCA: { value: 0.0012 }, uContrast: { value: 1.06 },
  },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float uTime, uSat, uVig, uGrain, uCA, uContrast; uniform vec3 uLift, uGain; uniform vec2 uRes; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
    void main(){
      vec2 c = vUv - 0.5;
      vec3 col;
      col.r = texture2D(tDiffuse, vUv - c*uCA*2.0).r;
      col.g = texture2D(tDiffuse, vUv).g;
      col.b = texture2D(tDiffuse, vUv + c*uCA*2.0).b;
      col = (col - 0.5) * uContrast + 0.5;
      float l = dot(col, vec3(0.2126,0.7152,0.0722));
      col = mix(vec3(l), col, uSat);
      col = col * uGain + uLift * (1.0 - col);
      // warm highlights / cool shadows split tone
      col += vec3(0.025,0.01,-0.02) * smoothstep(0.5,1.0,l) + vec3(-0.01,0.0,0.02) * smoothstep(0.4,0.0,l);
      float v = smoothstep(0.95, 0.25, length(c*vec2(1.0, 0.75)));
      col *= mix(1.0 - uVig, 1.0, v);
      float g = h(vUv*uRes + fract(uTime*7.13)*100.0) - 0.5;
      col += g * uGrain * (1.0 - l*0.6);
      gl_FragColor = vec4(clamp(col,0.0,1.0), 1.0);
    }`,
});
composer.addPass(grade);

// ---------- text overlays ----------
function drawText(o) {
  const { text, x, y, size = 40, font = 'Cormorant', weight = '600', style = 'normal', alpha = 1, spacing = 0, color = '#fff', shadow = true, align = 'center' } = o;
  ctx2d.save();
  ctx2d.globalAlpha = Math.max(0, Math.min(1, alpha));
  ctx2d.font = `${style} ${weight} ${size}px ${font}`;
  ctx2d.textAlign = align; ctx2d.textBaseline = 'middle';
  if ('letterSpacing' in ctx2d) ctx2d.letterSpacing = `${spacing}px`;
  if (shadow) { ctx2d.shadowColor = 'rgba(0,0,0,0.75)'; ctx2d.shadowBlur = size * 0.25; ctx2d.shadowOffsetY = 2; }
  ctx2d.fillStyle = color;
  ctx2d.fillText(text, x, y);
  ctx2d.restore();
}

export const STAGE = {
  THREE, scene, camera, renderer, world, juno, rowan, lanterns, lastLantern, handLantern, workLantern, shelfLanterns, potato, boat,
  mapUnfinished, mapFinished, sketch, lightPool, allLanterns, sky, mist, fx, sapling, youngTree, HILLTOP, water, U, dof, bloom, grade,
  OUT_W, OUT_H, GL_W, GL_H, drawText, ctx2d, FPS,
};

function renderFrame(frame) {
  const t = frame / FPS;
  const plan = FILM.apply(STAGE, t);   // sets world state, camera, returns overlay plan
  U.uTime.value = plan.time ?? t;
  grade.uniforms.uTime.value = t;
  const barH = Math.round((OUT_H - GL_H) / 2);
  ctx2d.globalAlpha = 1;
  ctx2d.fillStyle = '#000'; ctx2d.fillRect(0, 0, OUT_W, OUT_H);
  if (!plan.black) {
    renderer.shadowMap.needsUpdate = true;
    renderReflection();
    composer.render();
    ctx2d.drawImage(glCanvas, 0, barH);
  }
  if (plan.dissolveFrom) {
    // render the outgoing shot on top with fading alpha
    const p2 = FILM.applyShot(STAGE, plan.dissolveFrom.shot, plan.dissolveFrom.t, t);
    U.uTime.value = p2.time ?? t;
    renderer.shadowMap.needsUpdate = true;
    renderReflection();
    composer.render();
    ctx2d.globalAlpha = plan.dissolveFrom.alpha;
    ctx2d.drawImage(glCanvas, 0, barH);
    ctx2d.globalAlpha = 1;
  }
  if (plan.fade > 0) { ctx2d.fillStyle = `rgba(0,0,0,${plan.fade})`; ctx2d.fillRect(0, barH, OUT_W, GL_H); }
  for (const txt of plan.texts ?? []) drawText({ ...txt, x: txt.x * OUT_W, y: txt.y * OUT_H, size: txt.size * OUT_W / 1920 });
  return out;
}

window.renderFrame = (frame, quality = 0.93) => { renderFrame(frame); return out.toDataURL('image/jpeg', quality); };
window.renderOnly = (frame) => { renderFrame(frame); return true; };
window.FILM = FILM;
window.needsLocalizedFrame = (f) => needsLocalizedFrame(f / FPS);
window.STAGE = STAGE;
window.packSheet = () => packSheet(6).toDataURL('image/png');
await loadFonts();
// warm up shaders
renderFrame(0);
window.filmReady = true;
document.title = 'ready';
