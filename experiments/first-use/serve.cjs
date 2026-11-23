const {createServer} = require('node:http');
const {createReadStream} = require('node:fs');
const {stat} = require('node:fs/promises');
const {extname, resolve} = require('node:path');

const root = resolve(__dirname, '../..');
const port = Number(process.argv[2] || 8765);
const prefix = 'experiments/first-use/';
const {clips} = require('../../pool_manifest.json');
const files = new Set([
    'hand_captcha_prod.html', 'pool_manifest.json',
    ...clips.flatMap(clip => [clip.video_file, clip.landmarks_file]),
    ...['index.html', 'app.js', 'study.js', 'first-use.css', 'palm.svg', 'intro-illustration.png'].map(name => prefix + name)
]);
const types = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
    '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.png': 'image/png'
};

createServer(async (req, res) => {
    const finish = code => res.writeHead(code).end();
    if (!['GET', 'HEAD'].includes(req.method)) return finish(405);
    if (!['localhost:' + port, '127.0.0.1:' + port].includes(req.headers.host)) return finish(403);
    let name;
    try { name = new URL(req.url, 'http://localhost').pathname.slice(1); }
    catch { return finish(400); }
    const entry = !name || name === prefix ? prefix + 'index.html' : name;
    if (!files.has(entry)) return finish(404);
    const filename = resolve(root, entry);
    const info = await stat(filename).catch(() => null);
    if (!info?.isFile()) return finish(404);

    const headers = {'Content-Type': types[extname(entry)], 'Accept-Ranges': 'bytes'};
    let start = 0;
    let end = info.size - 1;
    if (req.headers.range) {
        const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
        if (range) {
            start = Number(range[1]);
            if (range[2]) end = Math.min(end, Number(range[2]));
        }
        if (!range || start > end) return res.writeHead(416, {'Content-Range': 'bytes */' + info.size}).end();
        headers['Content-Range'] = `bytes ${start}-${end}/${info.size}`;
    }
    headers['Content-Length'] = end - start + 1;
    res.writeHead(req.headers.range ? 206 : 200, headers);
    if (req.method === 'HEAD') return res.end();
    createReadStream(filename, {start, end}).on('error', () => res.destroy()).pipe(res);
}).listen(port, '127.0.0.1', () => console.log(`http://127.0.0.1:${port}/${prefix}`));
