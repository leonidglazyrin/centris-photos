import * as THREE from 'three';
import { U } from './materials.js';
import { fbm, clamp, lerp, mulberry32 } from './util.js';

// Colour script keyed by time of day (hours). Hand-graded for a warm, cozy look.
const KEYS = [
  { t: 0.0, zen: '#060a1c', hor: '#16223f', sun: '#8fa8ff', sunI: 0.55, amb: '#2c3a68', ambI: 0.7, fog: '#101a33', fogD: 0.010 },
  { t: 4.6, zen: '#0b1330', hor: '#2a3257', sun: '#8fa8ff', sunI: 0.35, amb: '#2b3660', ambI: 0.55, fog: '#1b2442', fogD: 0.012 },
  { t: 5.5, zen: '#27335f', hor: '#d98b86', sun: '#ff9a6a', sunI: 0.5, amb: '#6f6a92', ambI: 0.7, fog: '#b98a92', fogD: 0.011 },
  { t: 6.4, zen: '#5c7fbf', hor: '#ffc39a', sun: '#ffb27a', sunI: 1.6, amb: '#a7a9c9', ambI: 0.95, fog: '#f0c4a8', fogD: 0.0075 },
  { t: 8.5, zen: '#4f95e0', hor: '#cfe4f2', sun: '#fff0d6', sunI: 2.6, amb: '#cad8e8', ambI: 1.1, fog: '#d8e8f2', fogD: 0.0042 },
  { t: 12.5, zen: '#3e8ae2', hor: '#c3e0f6', sun: '#fff8ec', sunI: 3.0, amb: '#cfdcea', ambI: 1.15, fog: '#cfe4f4', fogD: 0.0036 },
  { t: 16.3, zen: '#5f93d4', hor: '#fbd9a8', sun: '#ffd49a', sunI: 2.7, amb: '#c9c3c2', ambI: 1.05, fog: '#f1dcc0', fogD: 0.0045 },
  { t: 17.9, zen: '#5a6fb0', hor: '#ffa56e', sun: '#ffa060', sunI: 2.1, amb: '#b9a0a8', ambI: 0.9, fog: '#f0b48e', fogD: 0.008 },
  { t: 18.8, zen: '#34407f', hor: '#ff7b52', sun: '#ff7040', sunI: 1.1, amb: '#8a7198', ambI: 0.75, fog: '#c7787a', fogD: 0.009 },
  { t: 19.6, zen: '#161d45', hor: '#8f5a78', sun: '#9fb0ff', sunI: 0.3, amb: '#3f3f70', ambI: 0.6, fog: '#3a3558', fogD: 0.011 },
  { t: 20.8, zen: '#070c22', hor: '#1d2a50', sun: '#9fb4ff', sunI: 0.55, amb: '#2c3a68', ambI: 0.7, fog: '#121b36', fogD: 0.010 },
  { t: 24.0, zen: '#060a1c', hor: '#16223f', sun: '#8fa8ff', sunI: 0.55, amb: '#2c3a68', ambI: 0.7, fog: '#101a33', fogD: 0.010 },
];
const KC = KEYS.map((k) => ({ ...k, zen: new THREE.Color(k.zen), hor: new THREE.Color(k.hor), sun: new THREE.Color(k.sun), amb: new THREE.Color(k.amb), fog: new THREE.Color(k.fog) }));

export function sampleTOD(t) {
  t = ((t % 24) + 24) % 24;
  let i = 0;
  while (i < KC.length - 2 && KC[i + 1].t < t) i++;
  const a = KC[i], b = KC[i + 1];
  const k = clamp((t - a.t) / (b.t - a.t), 0, 1);
  const s = k * k * (3 - 2 * k);
  const c = (p) => a[p].clone().lerp(b[p], s);
  return { zen: c('zen'), hor: c('hor'), sun: c('sun'), amb: c('amb'), fog: c('fog'), sunI: lerp(a.sunI, b.sunI, s), ambI: lerp(a.ambI, b.ambI, s), fogD: lerp(a.fogD, b.fogD, s) };
}

// Sun rises in the east (+x), arcs over the south (+z), sets in the west.
export function sunDirection(t, azOffset = 0) {
  const th = (t - 5.5) / 13.5 * Math.PI;
  const v = new THREE.Vector3(Math.cos(th), Math.sin(th) * 0.9, 0.35 + Math.sin(th) * 0.25);
  v.applyAxisAngle(new THREE.Vector3(0, 1, 0), azOffset);
  return v.normalize();
}

export function createSky(scene) {
  const skyU = {
    uZen: { value: new THREE.Color() }, uHor: { value: new THREE.Color() }, uSun: { value: new THREE.Vector3() },
    uSunCol: { value: new THREE.Color() }, uMoon: { value: new THREE.Vector3() }, uStars: { value: 0 }, uTime: U.uTime,
    uSunVis: { value: 1 }, uMoonVis: { value: 1 },
  };
  const sky = new THREE.Mesh(new THREE.SphereGeometry(900, 48, 24), new THREE.ShaderMaterial({
    uniforms: skyU, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: `
      uniform vec3 uZen, uHor, uSunCol, uSun, uMoon; uniform float uStars, uTime, uSunVis, uMoonVis;
      varying vec3 vDir;
      float h3(vec3 p){ p = fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
      // square disc like a blocky sun
      float sq(vec3 d, vec3 c, float size){
        vec3 up = abs(c.y) > 0.99 ? vec3(1.0,0.0,0.0) : vec3(0.0,1.0,0.0);
        vec3 r = normalize(cross(up, c)); vec3 u = cross(c, r);
        if (dot(d,c) < 0.0) return 0.0;
        vec2 q = vec2(dot(d,r), dot(d,u)) / size;
        return step(max(abs(q.x),abs(q.y)), 1.0);
      }
      void main(){
        vec3 d = normalize(vDir);
        float h = clamp(d.y, -0.2, 1.0);
        float g = pow(max(h,0.0), 0.55);
        vec3 col = mix(uHor, uZen, g);
        if (d.y < 0.0) col = mix(uHor, uHor*0.7, clamp(-d.y*4.0,0.0,1.0));
        float sd = max(dot(d, uSun), 0.0);
        col += uSunCol * (pow(sd, 8.0)*0.35 + pow(sd, 64.0)*0.6) * uSunVis;
        col += uSunCol * 6.0 * sq(d, uSun, 0.045) * uSunVis;
        float md = sq(d, uMoon, 0.032);
        vec3 mc = vec3(0.86,0.9,1.0) * (0.85 + 0.15*h3(floor(d*400.0)));
        col = mix(col, mc*2.2, md * uMoonVis);
        col += vec3(0.5,0.6,1.0) * pow(max(dot(d,uMoon),0.0), 40.0) * 0.25 * uMoonVis;
        if (uStars > 0.0 && d.y > 0.0) {
          vec3 p = d * 260.0; vec3 cell = floor(p);
          float s = h3(cell);
          if (s > 0.9965) {
            vec3 f = fract(p) - 0.5;
            float tw = 0.6 + 0.4*sin(uTime*3.0 + s*400.0);
            float st = smoothstep(0.26, 0.0, max(abs(f.x),max(abs(f.y),abs(f.z))));
            col += vec3(1.0,0.95,0.85) * st * tw * uStars * smoothstep(0.0,0.25,d.y) * 1.6;
          }
        }
        gl_FragColor = vec4(col, 1.0);
      }`,
  }));
  sky.frustumCulled = false;
  sky.renderOrder = -10;
  scene.add(sky);

  // Blocky clouds: flat cuboids on a grid, sampled from noise.
  const cloudGeo = new THREE.BoxGeometry(1, 1, 1);
  const cells = [];
  const CS = 12;
  for (let gz = -40; gz < 40; gz++) for (let gx = -40; gx < 40; gx++) {
    const n = fbm(gx * 0.13, gz * 0.13, 3, 42);
    if (n > 0.56) cells.push([gx * CS, gz * CS]);
  }
  const cloudMat = new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.82, emissive: new THREE.Color(0x000000), fog: true });
  const clouds = new THREE.InstancedMesh(cloudGeo, cloudMat, cells.length);
  const m4 = new THREE.Matrix4();
  cells.forEach(([x, z], i) => { m4.makeScale(CS, 4, CS); m4.setPosition(x, 0, z); clouds.setMatrixAt(i, m4); });
  clouds.position.y = 95;
  clouds.frustumCulled = false;
  scene.add(clouds);

  // lights
  const sun = new THREE.DirectionalLight(0xffffff, 2);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.04;
  sun.shadow.radius = 3;
  const sc = sun.shadow.camera;
  sc.left = -45; sc.right = 45; sc.top = 45; sc.bottom = -45; sc.near = 1; sc.far = 400;
  scene.add(sun, sun.target);
  const hemi = new THREE.HemisphereLight(0xbcd6f0, 0x6b5a45, 1.0);
  scene.add(hemi);
  scene.fog = new THREE.FogExp2(0xcfe4f4, 0.006);

  function set({ tod, center, sunAz = 0, fogMul = 1, cloudDrift = 0, shadowSize = 45, stars = null, time = 0, overcast = 0, sunMul = 1, ambMul = 1 }) {
    const k = sampleTOD(tod);
    if (overcast > 0) {
      const grey = new THREE.Color('#b9c2cc'), greyZ = new THREE.Color('#8d9aa8');
      const lum = (k.zen.r + k.zen.g + k.zen.b) / 3 + 0.15;
      k.zen.lerp(greyZ.clone().multiplyScalar(Math.min(1, lum * 1.4)), overcast);
      k.hor.lerp(grey.clone().multiplyScalar(Math.min(1, lum * 1.6)), overcast);
      k.fog.lerp(k.hor, overcast);
      k.sunI *= 1 - overcast * 0.65; k.ambI *= 1 + overcast * 0.25;
    }
    k.sunI *= sunMul; k.ambI *= ambMul;
    const sd = sunDirection(tod, sunAz);
    const md = sd.clone().multiplyScalar(-1); md.y = Math.abs(md.y) * 0.8 + 0.25; md.normalize();
    const sunUp = clamp((sd.y + 0.05) / 0.2, 0, 1);
    const lightDir = sd.y > -0.02 ? sd : md;
    skyU.uZen.value.copy(k.zen); skyU.uHor.value.copy(k.hor);
    skyU.uSun.value.copy(sd); skyU.uMoon.value.copy(md);
    skyU.uSunCol.value.copy(new THREE.Color('#ffd9a8').lerp(new THREE.Color('#ffffff'), clamp(sd.y * 2, 0, 1)));
    skyU.uSunVis.value = clamp((sd.y + 0.06) / 0.1, 0, 1) * (1 - overcast);
    skyU.uMoonVis.value = 1 - sunUp * 0.85;
    skyU.uStars.value = (stars ?? clamp((-sd.y - 0.02) / 0.15, 0, 1)) * (1 - overcast);
    sun.color.copy(k.sun); sun.intensity = k.sunI * (sd.y > -0.02 ? clamp(sd.y / 0.08, 0.15, 1) : 1);
    sun.position.copy(center).addScaledVector(lightDir, 150);
    sun.target.position.copy(center);
    sc.left = -shadowSize; sc.right = shadowSize; sc.top = shadowSize; sc.bottom = -shadowSize;
    sc.updateProjectionMatrix();
    hemi.color.copy(k.amb).lerp(k.zen, 0.25); hemi.groundColor.copy(k.amb).multiplyScalar(0.45).lerp(new THREE.Color('#5a4a3a'), 0.3);
    hemi.intensity = k.ambI;
    scene.fog.color.copy(k.fog);
    scene.fog.density = k.fogD * fogMul;
    U.uSkyHorizon.value.copy(k.hor); U.uSkyZenith.value.copy(k.zen);
    U.uSunDir.value.copy(lightDir); U.uSunColor.value.copy(k.sun);
    // clouds tint with sky
    cloudMat.color.copy(k.hor).lerp(new THREE.Color('#ffffff'), 0.55);
    cloudMat.emissive.copy(k.hor).multiplyScalar(0.35);
    clouds.position.x = 88 + cloudDrift + time * 0.6;
    clouds.position.z = 98;
    return { k, sd, night: 1 - clamp((sd.y + 0.1) / 0.25, 0, 1) };
  }
  return { set, sun, hemi, clouds, sky };
}
