// Frame-accurate offline renderer: drives the film in headless Chromium and
// pipes JPEG frames into ffmpeg (libx264).
//   node render.mjs --from 0 --to 7200 --out out/seg.mp4 [--w 1920] [--stills 10,500]
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []));
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const FFMPEG = process.env.FFMPEG || '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2';
const W = +(args.w ?? 1920);

const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(p)] ?? 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, r));
const port = server.address().port;

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl', '--disable-gpu-sandbox'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 450 } });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text().slice(0, 400)); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.goto(`http://localhost:${port}/index.html?w=${W}&lang=${args.lang ?? 'en'}`);
await page.waitForFunction(() => window.filmReady === true, null, { timeout: 600000 });

const decode = (d) => Buffer.from(d.slice(d.indexOf(',') + 1), 'base64');
if (args.stills) {
  fs.mkdirSync(args.dir ?? 'stills', { recursive: true });
  for (const f of args.stills.split(',').map(Number)) {
    const t0 = Date.now();
    const d = await page.evaluate((f) => window.renderFrame(f, 0.9), f);
    fs.writeFileSync(path.join(args.dir ?? 'stills', `f${String(f).padStart(5, '0')}.jpg`), decode(d));
    console.log('still', f, (f / 24).toFixed(2) + 's', Date.now() - t0, 'ms');
  }
} else if (args.localized) {
  // Render only the frames whose pixels differ by language (text, map), as JPEGs.
  const dir = args.localized; fs.mkdirSync(dir, { recursive: true });
  const from = +(args.from ?? 0), to = +(args.to ?? 7200);
  let n = 0; const t0 = Date.now();
  for (let f = from; f < to; f++) {
    const file = path.join(dir, `${String(f + 1).padStart(5, '0')}.jpg`);
    if (fs.existsSync(file)) continue;
    if (!(await page.evaluate((f) => window.needsLocalizedFrame(f), f))) continue;
    const d = await page.evaluate((f) => window.renderFrame(f, 0.95), f);
    fs.writeFileSync(file + '.tmp', decode(d)); fs.renameSync(file + '.tmp', file);
    if (++n % 48 === 0) console.log(`frame ${f} rendered ${n} ${((Date.now() - t0) / 1000 / n).toFixed(2)}s/f`);
  }
  console.log('localized done', from, to, n);
} else if (args.sheet) {
  const d = await page.evaluate(() => window.packSheet());
  fs.writeFileSync(args.sheet, decode(d));
} else {
  const from = +(args.from ?? 0), to = +(args.to ?? 7200);
  const ff = spawn(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '24', '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p', '-tune', 'film', args.out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = from; f < to; f++) {
    const d = await page.evaluate((f) => window.renderFrame(f, 0.95), f);
    if (!ff.stdin.write(decode(d))) await new Promise((r) => ff.stdin.once('drain', r));
    if ((f - from) % 48 === 0) {
      const el = (Date.now() - t0) / 1000, done = f - from + 1;
      console.log(`frame ${f} (${done}/${to - from}) ${(el / done).toFixed(2)}s/f eta ${((to - from - done) * el / done / 60).toFixed(1)}m`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
}
await browser.close();
server.close();
