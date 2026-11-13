"""Local headless Chrome checks for every UI combination at two viewport sizes.

Requires websockets in the test environment. Screenshots/profile stay outside Git.
No real camera, model, participant or private media is used by this preview check.
"""
import argparse
import asyncio
import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.request import Request,urlopen

import websockets
from experiments.preview_server import handler_for

ROOT=Path(__file__).resolve().parents[2]
STUB="""window.Hands=class {async initialize(){}setOptions(o){window.fixtureHandsOptions=o;}onResults(fn){this.fn=fn;}
async send({image}){window.fixtureInputWasRaw=image===cv;const p=FRAMING_GUIDE_POSE.map(([x,y])=>({x,y,z:0}));
this.fn({image,multiHandLandmarks:[p],multiHandedness:[{label:'Right',score:1}],multiHandWorldLandmarks:[p]});}};
window.drawConnectors=()=>{};window.drawLandmarks=()=>{};window.HAND_CONNECTIONS=[];"""


class CDP:
    def __init__(self,connection):self.connection=connection;self.index=0;self.errors=[];self.requests=[];self.fulfilled=0
    async def call(self,method,params=None):
        self.index+=1;index=self.index
        await self.connection.send(json.dumps({'id':index,'method':method,'params':params or {}}))
        while True:
            reply=json.loads(await asyncio.wait_for(self.connection.recv(),10))
            if reply.get('method')=='Runtime.exceptionThrown':self.errors.append(reply['params'])
            if reply.get('method')=='Network.requestWillBeSent':self.requests.append(reply['params']['request']['url'])
            if reply.get('method')=='Fetch.requestPaused':
                self.index+=1;self.fulfilled+=1
                await self.connection.send(json.dumps({'id':self.index,'method':'Fetch.fulfillRequest','params':{
                    'requestId':reply['params']['requestId'],'responseCode':200,
                    'responseHeaders':[{'name':'Content-Type','value':'application/javascript'},{'name':'Cache-Control','value':'no-store'}],
                    'body':base64.b64encode(STUB.encode()).decode()}}))
            if reply.get('id')==index:
                if 'error' in reply:raise RuntimeError('Browser protocol command failed: '+method)
                return reply.get('result',{})
    async def evaluate(self,expression):
        result=await self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError('Browser evaluation failed')
        return result['result'].get('value')


async def check(port,base,output,ffmpeg=None):
    request=Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')
    with urlopen(request,timeout=3) as response:tab=json.load(response)
    async with websockets.connect(tab['webSocketDebuggerUrl'],max_size=20*1024**2) as connection:
        cdp=CDP(connection)
        for domain in ('Page','Runtime','Network'):await cdp.call(domain+'.enable')
        checked=[]
        for width,height in ((1280,900),(390,844)):
            await cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
            for mask in range(64):
                await cdp.call('Page.navigate',{'url':base+f'/experiments/prod_ui_factorial/run.html?preview=1&condition={mask}'})
                await cdp.call('Page.bringToFront')
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    if await cdp.evaluate(f"document.body?.dataset.studyReady==='true'&&window.UIStudy?.config.mask==={mask}&&UIStudy.preview"):break
                    await asyncio.sleep(.03)
                else:raise RuntimeError('Preview did not become ready')
                row=await cdp.evaluate('''(()=>{
                  const cfg=UIStudy.config,canvas=document.querySelector('.study-target');
                  const pixel=()=>[...canvas.getContext('2d').getImageData(320,326,1,1).data];
                  UIStudy.freezeAt(0);const first=pixel(),start=UIStudy.getState();
                  UIStudy.freezeAt(1000);const last=pixel(),end=UIStudy.getState();
                  UIStudy.freezeAt(750);const middle=pixel(),half=UIStudy.getState();
                  const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
                  const hints=[...document.querySelectorAll('.palm-ui-help[aria-controls]')];
                  const camera=document.querySelector('.camera-area').getBoundingClientRect();
                  return {condition:cfg.mask,duplicates:ids.length-new Set(ids).size,
                    overflow:document.documentElement.scrollWidth>innerWidth,
                    selection:!!document.getElementById('selectionState'),
                    overlay:getComputedStyle(document.querySelector('.trial-content>.trial-panel')).display==='none',
                    hints:hints.length,hintTargets:hints.every(h=>!!document.getElementById(h.getAttribute('aria-controls'))),
                    cameraHeight:camera.height,cameraWidth:camera.width,first,last,middle,start,end,half,
                    preview:UIStudy.preview,humanEffects:UIStudy.snapshot().human_effects_verified};
                })()''')
                reveal=bool(mask&32)
                assert row['condition']==mask and row['preview'] and not row['humanEffects']
                assert row['duplicates']==0 and not row['overflow'] and row['hintTargets']
                assert row['selection']==bool(mask&1) and row['overlay']==bool(mask&2)
                assert row['hints']==sum(bool(mask&bit) for bit in (4,8,16))
                assert row['cameraHeight']>=100 and row['cameraWidth']>=100
                assert row['start']['gate_blocked'] and row['half']['gate_blocked'] and not row['end']['gate_blocked']
                assert row['start']['reveal_alpha']==(1 if reveal else 0)
                assert row['half']['reveal_alpha']==(.5 if reveal else 0)
                assert row['end']['reveal_alpha']==0
                if reveal:
                    assert row['first']!=row['last']
                    assert all(abs(m-(a+b)/2)<=1 for a,b,m in zip(row['first'],row['last'],row['middle']))
                else:assert row['first']==row['middle']==row['last']
                await asyncio.sleep(.03)
                png=await cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
                (output/f'ui-{mask:02d}-{width}.png').write_bytes(base64.b64decode(png['data']))
                checked.append({'condition':mask,'width':width,'passed':True})
        assert not cdp.errors,'JavaScript errors occurred'
        assert not [url for url in cdp.requests if url.startswith(('https:','http:')) and not url.startswith(base+'/')], 'External request occurred'
        (output/'preview_checks.json').write_text(json.dumps({'cases':checked,'javascript_errors_n':0,'all_passed':True}),encoding='utf8')
        print('Preview checks passed: 64 conditions x 2 viewports',flush=True)
        runtime_cases=0
        if ffmpeg:
            assets=output/'synthetic-runtime-assets';assets.mkdir()
            pose=await cdp.evaluate('FRAMING_GUIDE_POSE');names=await cdp.evaluate('LN')
            for name,filters in (('raw',[]),('masked',['-vf','drawbox=x=220:y=226:w=200:h=200:color=black:t=fill'])):
                subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-n','-f','lavfi','-i',
                    'color=c=0xcda888:s=640x480:r=24:d=2',*filters,'-an','-c:v','libx264','-pix_fmt','yuv420p',str(assets/(name+'.mp4'))],check=True)
            points={name:{'x':p[0]*640,'y':p[1]*480,'z':0} for name,p in zip(names,pose)}
            (assets/'points.json').write_text(json.dumps({'video_info':{'width':640,'height':480,'fps':24},
                'frames':[{'frame_idx':i,'detected':True,'landmarks_px':points} for i in range(48)]}),encoding='utf8')
            await cdp.call('Fetch.enable',{'patterns':[{'urlPattern':'https://unpkg.com/*','requestStage':'Request'}]})
            await cdp.call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
            for mask in range(64):
                await cdp.call('Page.navigate',{'url':base+f'/experiments/prod_ui_factorial/run.html?condition={mask}'})
                await cdp.call('Page.bringToFront')
                deadline=time.monotonic()+8
                while not await cdp.evaluate(f"document.body?.dataset.studyReady==='true'&&window.UIStudy?.config.mask==={mask}&&!UIStudy.preview"):
                    if time.monotonic()>deadline:raise RuntimeError('Runtime UI not ready')
                    await asyncio.sleep(.03)
                root=(await cdp.call('DOM.getDocument'))['root']['nodeId']
                for field,name in (('studyMasked','masked.mp4'),('studyRaw','raw.mp4'),('studyLandmarks','points.json')):
                    node=(await cdp.call('DOM.querySelector',{'nodeId':root,'selector':'#'+field}))['nodeId']
                    await cdp.call('DOM.setFileInputFiles',{'nodeId':node,'files':[str(assets/name)]})
                await cdp.evaluate("document.getElementById('studyFamily').value='synthetic-fixture';document.getElementById('studyReviewed').checked=true;document.getElementById('studyBegin').click();true")
                deadline=time.monotonic()+10
                while not await cdp.evaluate("UIStudy.snapshot().events.some(e=>e.event==='prelude_started')"):
                    state=await cdp.evaluate('UIStudy.snapshot().outcome')
                    if state not in ('not_started','running') or time.monotonic()>deadline:
                        debug=await cdp.evaluate("({phase,selectedHand,frames:sessionLog.length,aborted:selectionRunAborted,ready:cv.readyState,cameraError:document.getElementById('cameraPlaceholder').textContent,events:UIStudy.snapshot().events,errors:document.getElementById('studyError')?.textContent})")
                        (output/'runtime_failure.json').write_text(json.dumps({'mask':mask,'state':debug,'browser_errors':cdp.errors},indent=2),encoding='utf8')
                        raise RuntimeError(f'Synthetic runtime start failed for condition {mask}: {state}')
                    await asyncio.sleep(.02)
                state=await cdp.evaluate('UIStudy.getState()');assert state['gate_blocked']
                frames=await cdp.evaluate('sessionLog.length')
                await asyncio.sleep(.2)
                assert await cdp.evaluate('UIStudy.getState().gate_blocked')
                assert await cdp.evaluate('sessionLog.length')==frames
                deadline=time.monotonic()+4
                while not await cdp.evaluate("UIStudy.snapshot().events.some(e=>e.event==='prelude_finished')"):
                    if time.monotonic()>deadline:raise RuntimeError('Synthetic prelude did not finish')
                    await asyncio.sleep(.02)
                assert await cdp.evaluate('UIStudy.snapshot().outcome')=='running'
                assert await cdp.evaluate('window.fixtureInputWasRaw')
                assert await cdp.evaluate('window.fixtureHandsOptions.maxNumHands')==(2 if mask&1 else 1)
                await cdp.evaluate("document.getElementById('studyStop').click();true")
                assert await cdp.evaluate("camStream.getTracks().every(t=>t.readyState==='ended')")
                assert await cdp.evaluate('UIStudy.snapshot().outcome')=='user_aborted'
                runtime_cases+=1
                (output/'runtime_progress.json').write_text(json.dumps({'passed_conditions':list(range(runtime_cases))}),encoding='utf8')
                if runtime_cases%8==0:print(f'Synthetic runtime checks passed: {runtime_cases}/64',flush=True)
            assert not cdp.errors,'JavaScript errors in synthetic runtime'
        return {'scope':'synthetic_ui_preview_and_pixel_checks_not_human_effects','conditions_n':64,
                'viewport_cases_n':len(checked),'javascript_errors_n':len(cdp.errors),
                'synthetic_runtime_cases_n':runtime_cases,
                'all_passed':True,'real_camera_used':False,'model_used':False,'human_effects_verified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome',type=Path,default=Path('C:/Program Files/Google/Chrome/Application/chrome.exe'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ffmpeg',type=Path,help='Also run all 64 live paths with generated media and a synthetic detector/camera')
    args=parser.parse_args()
    output=args.output.resolve()
    if 'private_artifacts' not in output.parts or any((p/'.git').exists() for p in output.parents):
        raise ValueError('Use a new private_artifacts directory outside Git')
    output.mkdir(parents=True,exist_ok=False)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(ROOT));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    profile=output/'chrome-profile'
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    process=subprocess.Popen([str(args.chrome),'--headless=new','--no-first-run','--no-default-browser-check',
        '--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions',
        '--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows',
        '--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',
        '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    try:
        deadline=time.monotonic()+10;port_file=profile/'DevToolsActivePort'
        while not port_file.exists() and time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('Headless browser exited')
            time.sleep(.03)
        port=int(port_file.read_text().splitlines()[0]);base=f'http://127.0.0.1:{server.server_port}'
        result=asyncio.run(check(port,base,output,args.ffmpeg))
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
        server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
