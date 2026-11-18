const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const prefix = 'experiments/prod_live_motion/';
const visualBase = 'experiments/prod_usability_v5/';
const port = Number(process.argv[2] ?? 8772);
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'pool_manifest.json'), 'utf8'));
const allow = new Set([
  ...['index.html', 'motion.js', 'live.js', 'live.css'].map(file => prefix + file),
  ...['app.js', 'selector.js', 'ui.css'].map(file => visualBase + file),
  'pool_manifest.json',
  ...manifest.clips.flatMap(clip => [clip.video_file, clip.landmarks_file]),
]);
const types = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.mp4': 'video/mp4',
};

const server = http.createServer((req, res) => {
  const reject = status => { res.writeHead(status); res.end(); };
  if (![ '127.0.0.1:' + port, 'localhost:' + port ].includes(req.headers.host)) return reject(403);
  if (!['GET', 'HEAD'].includes(req.method)) return reject(405);
  let name;
  try { name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).slice(1); }
  catch { return reject(400); }
  if (!name || name === prefix) name = prefix + 'index.html';
  if (!allow.has(name)) return reject(404);
  const file = path.resolve(root, name);
  if (!file.startsWith(root + path.sep)) return reject(403);

  fs.stat(file, (error, info) => {
    if (error || !info.isFile()) return reject(404);
    let start = 0, end = info.size - 1;
    const range = req.headers.range;
    if (range) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      if (!match) return reject(416);
      start = Number(match[1]);
      if (match[2]) end = Math.min(end, Number(match[2]));
      if (start > end) return reject(416);
    }
    const headers = {
      'Content-Type': types[path.extname(file)], 'Content-Length': end - start + 1,
      'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    };
    if (range) headers['Content-Range'] = `bytes ${start}-${end}/${info.size}`;
    res.writeHead(range ? 206 : 200, headers);
    if (req.method === 'HEAD') return res.end();
    fs.createReadStream(file, { start, end }).on('error', () => res.destroy()).pipe(res);
  });
});

server.listen(port, '127.0.0.1', () => console.log(`http://127.0.0.1:${port}/${prefix}`));
