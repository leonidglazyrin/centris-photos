import * as THREE from 'three';

export const U = {
  uTime: { value: 0 },
  uTiles: { value: null },
  uSnow: { value: 0 },
  uSnowTile: { value: 0 },
  uEmit: { value: 0 },
  uEmitColor: { value: new THREE.Color('#ffb05a') },
  uWind: { value: 1 },
  uSkyHorizon: { value: new THREE.Color('#cfe6f5') },
  uSkyZenith: { value: new THREE.Color('#5aa0e8') },
  uSunDir: { value: new THREE.Vector3(0, 1, 0) },
  uSunColor: { value: new THREE.Color('#fff') },
  tReflect: { value: null },
  uTexMat: { value: new THREE.Matrix4() },
};

function voxelMaterial(cutout) {
  const m = new THREE.MeshLambertMaterial({ vertexColors: true, side: cutout ? THREE.DoubleSide : THREE.FrontSide });
  m.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, U);
    s.vertexShader = s.vertexShader
      .replace('#include <common>', `#include <common>
        attribute vec3 aData;
        varying vec3 vData;
        varying vec2 vTileUv;
        varying vec3 vWN;
        uniform float uTime;
        uniform float uWind;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vData = aData; vTileUv = uv; vWN = normal;
        if (aData.y > 0.0) {
          vec3 wp = (modelMatrix * vec4(position, 1.0)).xyz;
          float ph = wp.x * 0.7 + wp.z * 0.9;
          float sw = sin(uTime * 1.7 + ph) * 0.6 + sin(uTime * 2.9 + ph * 1.7) * 0.4;
          transformed.x += sw * 0.06 * aData.y * uWind;
          transformed.z += cos(uTime * 1.3 + ph) * 0.05 * aData.y * uWind;
        }`);
    s.fragmentShader = s.fragmentShader
      .replace('#include <common>', `#include <common>
        precision highp sampler2DArray;
        uniform sampler2DArray uTiles;
        uniform float uSnow; uniform float uSnowTile;
        uniform float uEmit; uniform vec3 uEmitColor; uniform float uTime;
        varying vec3 vData; varying vec2 vTileUv; varying vec3 vWN;`)
      .replace('#include <map_fragment>', `
        vec4 texel = texture(uTiles, vec3(vTileUv, vData.x));
        ${cutout ? 'if (texel.a < 0.5) discard;' : ''}
        diffuseColor.rgb *= texel.rgb;
        float emitMask = ${cutout ? '0.0' : '1.0 - texel.a'};
        if (uSnow > 0.0 && emitMask < 0.5) {
          float up = smoothstep(0.5, 0.9, vWN.y);
          float side = (1.0 - abs(vWN.y)) * step(0.72, vTileUv.y) * ${cutout ? '0.0' : '1.0'};
          vec3 snow = texture(uTiles, vec3(vTileUv, uSnowTile)).rgb;
          diffuseColor.rgb = mix(diffuseColor.rgb, snow * 1.05, clamp(max(up, side) * uSnow, 0.0, 1.0));
        }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float flick = 0.9 + 0.1 * sin(uTime * 7.0 + vTileUv.x * 3.0);
        totalEmissiveRadiance += uEmitColor * emitMask * uEmit * flick * 3.0;`);
  };
  m.customProgramCacheKey = () => (cutout ? 'vox-cut' : 'vox');
  return m;
}

export function createMaterials(tileTex) {
  U.uTiles.value = tileTex;
  const opaque = voxelMaterial(false);
  const cutout = voxelMaterial(true);
  // shadow pass needs alpha-tested leaves: custom depth material sampling the array
  const depthCut = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  depthCut.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, U);
    s.vertexShader = s.vertexShader
      .replace('#include <common>', `#include <common>
        attribute vec3 aData; varying vec3 vData; varying vec2 vTileUv;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vData = aData; vTileUv = uv;`);
    s.fragmentShader = s.fragmentShader
      .replace('#include <common>', `#include <common>
        precision highp sampler2DArray; uniform sampler2DArray uTiles;
        varying vec3 vData; varying vec2 vTileUv;`)
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        if (texture(uTiles, vec3(vTileUv, vData.x)).a < 0.5) discard;`);
  };
  depthCut.customProgramCacheKey = () => 'vox-depth-cut';
  return { opaque, cutout, depthCut };
}

// Tileable water normal map built from summed sine waves.
function waterNormals(size = 256) {
  const h = new Float32Array(size * size);
  const waves = [];
  for (let i = 0; i < 24; i++) {
    const a = i * 2.39996;
    const k = 1 + (i % 6);
    waves.push([Math.round(Math.cos(a) * k), Math.round(Math.sin(a) * k), 1 / (k * 1.2), i * 1.7]);
  }
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let v = 0;
    for (const [kx, ky, amp, ph] of waves) v += Math.sin((kx * x + ky * y) / size * Math.PI * 2 + ph) * amp;
    h[y * size + x] = v;
  }
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const dx = h[y * size + ((x + 1) % size)] - h[y * size + ((x - 1 + size) % size)];
    const dy = h[((y + 1) % size) * size + x] - h[((y - 1 + size) % size) * size + x];
    const n = new THREE.Vector3(-dx * 0.9, -dy * 0.9, 1).normalize();
    const i = (y * size + x) * 4;
    data[i] = (n.x * 0.5 + 0.5) * 255; data[i + 1] = (n.y * 0.5 + 0.5) * 255; data[i + 2] = (n.z * 0.5 + 0.5) * 255; data[i + 3] = 255;
  }
  const t = new THREE.DataTexture(data, size, size);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true;
  t.needsUpdate = true;
  return t;
}

export function createWaterMaterial() {
  const m = new THREE.MeshPhongMaterial({
    color: new THREE.Color('#2a6f9e'), transparent: true, opacity: 0.82, shininess: 180,
    specular: new THREE.Color('#ffffff'), normalMap: waterNormals(), normalScale: new THREE.Vector2(0.35, 0.35), depthWrite: false,
  });
  m.normalMap.repeat.set(24, 24);
  m.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, U);
    s.vertexShader = s.vertexShader.replace('#include <common>', `#include <common>
      uniform mat4 uTexMat;
      varying vec2 vWUv; varying vec3 vWPos; varying vec4 vRefl;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
      vWPos = (modelMatrix * vec4(position,1.0)).xyz; vWUv = vWPos.xz; vRefl = uTexMat * vec4(vWPos, 1.0);`);
    s.fragmentShader = s.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform float uTime; uniform vec3 uSkyHorizon; uniform vec3 uSkyZenith; uniform vec3 uSunDir; uniform vec3 uSunColor;
        uniform sampler2D tReflect;
        varying vec2 vWUv; varying vec3 vWPos; varying vec4 vRefl;`)
      .replace('#include <normal_fragment_maps>', `
        vec3 n1 = texture2D(normalMap, vWUv * 0.045 + vec2(uTime * 0.012, uTime * 0.007)).xyz * 2.0 - 1.0;
        vec3 n2 = texture2D(normalMap, vWUv * 0.09 + vec2(-uTime * 0.009, uTime * 0.013)).xyz * 2.0 - 1.0;
        vec3 mapN = normalize(vec3((n1.xy + n2.xy) * normalScale.x, 1.0));
        normal = normalize(tbn * mapN);`)
      .replace('#include <opaque_fragment>', `
        vec3 Vd = normalize(vViewPosition);
        float fres = 0.06 + 0.94 * pow(1.0 - clamp(dot(normal, Vd), 0.0, 1.0), 5.0);
        vec2 ruv = vRefl.xy / vRefl.w + (n1.xy + n2.xy) * 0.012;
        vec3 refl = texture2D(tReflect, ruv).rgb;
        vec3 diffPart = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
        vec3 specPart = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
        float rk = clamp(fres * 1.1 + 0.18, 0.0, 0.92);
        vec3 col = mix(diffPart, refl, rk) + specPart;
        gl_FragColor = vec4(col, mix(opacity, 1.0, rk));`);
    // Phong with normal map in world-space plane: provide tbn via USE_NORMALMAP_TANGENTSPACE (default)
  };
  m.customProgramCacheKey = () => 'water';
  return m;
}
