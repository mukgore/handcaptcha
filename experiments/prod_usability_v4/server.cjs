// Loopback only; serve this entry and its actual challenge dependencies, no directory listing.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),port=Number(process.argv[2]||8771);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'pool_manifest.json')));
const prefix='experiments/prod_usability_v4/';
const allowed=new Set(['pool_manifest.json',...manifest.clips.flatMap(c=>[c.video_file,c.landmarks_file]),
  ...['index.html','app.js','selector.js','ui.css'].map(p=>prefix+p)]);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.mp4':'video/mp4'};
const server=http.createServer((req,res)=>{
  function fail(code){res.writeHead(code,{'Content-Length':0});res.end();}
  if(!['127.0.0.1:'+port,'localhost:'+port].includes(req.headers.host))return fail(403);
  if(!['GET','HEAD'].includes(req.method))return fail(405);
  let name;try{name=decodeURIComponent(new URL(req.url,'http://localhost').pathname).slice(1);}catch{return fail(400);}
  if(!name||name===prefix)name=prefix+'index.html';
  if(!allowed.has(name))return fail(404);
  const file=path.resolve(root,name);if(!file.startsWith(root+path.sep))return fail(403);
  fs.stat(file,(error,stat)=>{
    if(error||!stat.isFile())return fail(404);
    let start=0,end=stat.size-1,status=200;
    if(req.headers.range){
      const m=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
      if(!m)return fail(416);start=Number(m[1]);end=m[2]?Math.min(Number(m[2]),end):end;
      if(start>end||start>=stat.size)return fail(416);status=206;
    }
    const headers={'Content-Type':types[path.extname(file)]||'application/octet-stream','Content-Length':end-start+1,
      'Accept-Ranges':'bytes','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'};
    if(status===206)headers['Content-Range']=`bytes ${start}-${end}/${stat.size}`;
    res.writeHead(status,headers);if(req.method==='HEAD')return res.end();
    fs.createReadStream(file,{start,end}).on('error',()=>res.destroy()).pipe(res);
  });
});
server.listen(port,'127.0.0.1',()=>console.log(`CAPTCHA usability: http://127.0.0.1:${port}/${prefix}`));
server.on('error',e=>{console.error(e.message);process.exitCode=1;});
