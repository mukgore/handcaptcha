/* Local design review: execute the original renderer, omit camera bootstrap. */
(() => {
    'use strict';
    const versions = {
        original: ['기존 화면', '원래 화면 구성을 비교 기준으로 보여 줍니다.'],
        a_copy: ['A · 기존 배너와 카메라 문구 강화', '화면 틀을 유지하고 손금 쪽을 렌즈로 향하라는 문구를 카메라 가까이에 둡니다.'],
        b_compare: ['B · 기존 카메라 패널에 비교 그림', '카메라 바로 위에 손바닥의 손금과 손등의 손톱을 나란히 보여 줍니다.'],
        c_guide: ['C · 기존 회색 가이드에 손금 추가', '기존 카메라 위 회색 손 가이드에 손금을 그려 어느 면을 보여야 하는지 보강합니다.']
    };
    let generation = 0;
    const fixture = `
      document.getElementById('loadingOverlay').classList.add('hidden');
      document.getElementById('kfProgress').innerHTML = '<div class="kf-dot active" id="kfd0">1</div><span class="kf-arrow">→</span><div class="kf-dot" id="kfd1">2</div><span class="kf-arrow">→</span><div class="kf-dot" id="kfd2">3</div>';
      document.getElementById('kfLabel').textContent = '자세 1/3';
      document.getElementById('kfInfo').textContent = '목표 영상 예시';
      document.getElementById('cameraPlaceholder').style.display = 'none';
      document.getElementById('frameCounter').textContent = '미리보기';
      for(const canvas of [rc,cc]) { canvas.width=640; canvas.height=480; canvas.style.display='block'; }
      rctx.fillStyle='#0f172a';rctx.fillRect(0,0,640,480);
      drawGhostSilhouette(FRAMING_GUIDE_POSE.map(p=>[p[0]*640,p[1]*480]),rctx,640,480,{skipClear:true,fillStyle:'#cda888',palm:true});
      rctx.fillStyle='#000';rctx.beginPath();rctx.arc(320,326,130,0,Math.PI*2);rctx.fill();
      ctx.fillStyle='#1e293b';ctx.fillRect(0,0,640,480);
      drawGhostSilhouette(FRAMING_GUIDE_POSE.map(p=>[(p[0]+.14)*640,(p[1]+.04)*480]),ctx,640,480,{skipClear:true,fillStyle:'#ad8568',palm:true});
      framingGuideStartTime=performance.now();drawFramingGuideOverlay(performance.now());
      for(const context of [rctx,ctx]) { context.font='14px sans-serif';context.fillStyle='#cbd5e1';context.fillText('UI preview / illustrative hand',14,24); }
      document.body.dataset.previewReady='true';
    `;
    async function show(version) {
        if (!versions[version]) return;
        const run = ++generation;
        document.querySelectorAll('[data-version]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.version===version)));
        document.getElementById('versionTitle').textContent = versions[version][0];
        document.getElementById('description').textContent = versions[version][1];
        const file = version==='original' ? '../../hand_captcha_prod.html' : version+'.html';
        document.getElementById('liveLink').href = file;
        const error = document.getElementById('loadError'); error.hidden = true;
        try {
            const response = await fetch(file);
            if (!response.ok) throw Error('HTTP '+response.status);
            const doc = new DOMParser().parseFromString(await response.text(),'text/html');
            // Preview only: prevent model/CDN/camera boot and freeze the intro.
            for (const s of doc.querySelectorAll('script[src]')) {
                if (!s.hasAttribute('data-palm-variant')) s.remove();
            }
            for (const s of doc.querySelectorAll('script:not([src])')) {
                if (!/\nbootstrap\(\);/.test(s.textContent)) throw Error('Production bootstrap changed; rebuild preview');
                s.textContent=s.textContent.replace(/\nbootstrap\(\);/,'\n/* Static UI preview: bootstrap omitted. */')
                    .replace('setTimeout(dismissIntroBanner, 8000);','/* Intro frozen for visual comparison. */');
            }
            doc.querySelectorAll('base').forEach(n=>n.remove());
            const base = doc.createElement('base'); base.href = new URL('../../',location.href).href;
            doc.head.prepend(base);
            doc.querySelectorAll('link[href*="fonts.googleapis.com"]').forEach(n=>n.remove());
            const script = doc.createElement('script'); script.textContent=fixture;doc.body.appendChild(script);
            if (run===generation) document.getElementById('preview').srcdoc='<!doctype html>\n'+doc.documentElement.outerHTML;
        } catch(e) {
            if(run===generation){error.hidden=false;error.textContent='미리보기를 불러오지 못했습니다. 저장소 루트에서 로컬 HTTP 서버로 열어 주세요. ('+e.message+')';}
        }
    }
    document.querySelectorAll('[data-version]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.version)));
    show('original');
})();
