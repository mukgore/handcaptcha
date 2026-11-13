/* Presentation-only additions to hand_captcha_prod.html. */
(() => {
    'use strict';
    const variants=(document.currentScript.dataset.palmVariants ?? document.currentScript.dataset.palmVariant ?? '').split(',').filter(Boolean);
    if (!variants.length || new Set(variants).size!==variants.length || variants.some(v=>!['copy','compare','guide'].includes(v))) return;
    for(const variant of variants){
    const camera = document.querySelector('.camera-area');
    const panel = camera.closest('.trial-panel');
    const header = panel.querySelector('.panel-header');
    const intro = document.querySelector('#introBanner > span');
    const caption = '손금이 보이는 손바닥을 카메라 렌즈로 향해 주세요.';
    intro.textContent = caption + ' 목표 자세를 순서대로 따라 해 주세요.';

    function handSvg(palm) {
        // Fixed explanatory icon, independent of the challenge/participant.
        return `<svg viewBox="0 0 80 108" aria-hidden="true" focusable="false">
          <path d="M23 99V70L7 51Q2 43 9 39Q13 37 18 43L25 51V22Q25 15 31 15Q37 15 37 22V43H39V12Q39 5 45 5Q51 5 51 12V43H53V20Q53 13 59 13Q65 13 65 20V49H67V34Q67 27 73 29Q77 30 77 36V70Q77 85 63 99Z" fill="${palm ? '#dbeafe' : '#f1f5f9'}" stroke="${palm ? '#2563eb' : '#94a3b8'}" stroke-width="3" stroke-linejoin="round"/>
          ${palm ? '<path d="M33 60Q48 53 65 58M35 72Q51 80 64 68M29 57Q42 65 38 86" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round"/>' : '<path d="M28 23H34V32H28ZM42 13H48V22H42ZM56 21H62V30H56ZM69 36H74V44H69Z" fill="#cbd5e1"/>'}
        </svg>`;
    }
    const help = document.createElement('button');
    help.type = 'button'; help.className = 'palm-ui-help';
    help.textContent = '손바닥 안내'; help.setAttribute('aria-expanded', 'true');
    header.insertBefore(help, document.getElementById('frameCounter'));
    let details;
    if (variant === 'copy') {
        details = document.createElement('div'); details.className = 'palm-ui-hint';
        details.innerHTML = '<strong>손금이 보이는 쪽 → 카메라 렌즈</strong><br>손 전체가 보이게 두고, 왼쪽 목표 자세를 따라 해 주세요.';
        panel.insertBefore(details, camera);
    } else if (variant === 'compare') {
        details = document.createElement('div'); details.className = 'palm-ui-compare';
        details.innerHTML = `<div class="palm-ui-example good">${handSvg(true)}<div><strong>이 면을 보여 주세요</strong><small>손금이 보이는 손바닥</small></div></div><div class="palm-ui-divider"></div><div class="palm-ui-example other">${handSvg(false)}<div><strong>반대쪽 면</strong><small>손톱이 보이는 손등</small></div></div>`;
        panel.insertBefore(details, camera);
    } else {
        details = document.createElement('div'); details.className = 'palm-ui-chip';
        details.innerHTML = `${handSvg(true)}<span><strong>손금 쪽을 렌즈로</strong><br>회색 손 안내에 손 전체를 맞춰 주세요.</span>`;
        camera.appendChild(details);
        // The original renderer runs under the camera's mirror transform.
        // Add only fixed palm creases, with the original guide's fade timing.
        if (typeof drawFramingGuideOverlay === 'function') {
            const original = drawFramingGuideOverlay;
            drawFramingGuideOverlay = function(now) {
                original(now);
                if (framingOverlayDone) return;
                const alpha = framingFadeStart === null ? .85 : .85 * Math.min(1, Math.max(0, 1 - (now - framingFadeStart) / FRAMING_FADE_MS));
                drawPalmCreases(ctx, cc.width, cc.height, alpha, now);
            };
        }
    }
    details.id = variants.length===1?'palmUiDetails':'palmUiDetails-'+variant;
    if(variants.length>1)help.textContent={copy:'문구 안내',compare:'그림 안내',guide:'손금 안내'}[variant];
    help.setAttribute('aria-controls', details.id);
    let autoHidden = false;
    function setVisible(visible) {
        details.classList.toggle('palm-ui-hidden', !visible);
        help.setAttribute('aria-expanded', String(visible));
    }
    help.addEventListener('click', () => {
        setVisible(details.classList.contains('palm-ui-hidden'));
    });
    const progress = document.getElementById('kfProgress');
    const result = document.getElementById('screenResult');
    function update() {
        // Existing progress DOM only controls hint visibility. Never claim
        // that a matched keyframe proves palm-facing input.
        const first = document.getElementById('kfd0');
        if (!autoHidden && ((first && first.classList.contains('done')) || result.classList.contains('active'))) {
            setVisible(false); autoHidden = true;
        }
    }
    const observer = new MutationObserver(update);
    observer.observe(progress, {subtree:true, attributes:true, attributeFilter:['class'], childList:true});
    observer.observe(result, {attributes:true, attributeFilter:['class']});
    addEventListener('pagehide', () => observer.disconnect(), {once:true});

    function drawPalmCreases(context, width, height, alpha, now) {
        context.save(); context.globalAlpha = alpha;
        // Emphasize the existing generic palm polygon and keep creases
        // inside it. The coordinates/fade still belong to the original guide.
        const guide = framingGuideFrame(now - framingGuideStartTime);
        context.beginPath();
        [0,5,9,13,17,1].forEach((index,i) => {
            const p = guide[index];
            if(i===0) context.moveTo(p[0]*width,p[1]*height);
            else context.lineTo(p[0]*width,p[1]*height);
        });
        context.closePath(); context.fillStyle = FRAMING_GUIDE_FILL;
        context.fill(); context.clip();
        context.strokeStyle = '#fff'; context.lineWidth = Math.max(2, width * .005);
        context.lineCap = 'round';
        const paths = [ [[.41,.58],[.49,.55],[.60,.59]], [[.43,.66],[.51,.72],[.60,.65]], [[.40,.59],[.48,.68],[.46,.79]] ];
        for (const p of paths) {
            context.beginPath(); context.moveTo(p[0][0]*width,p[0][1]*height);
            context.quadraticCurveTo(p[1][0]*width,p[1][1]*height,p[2][0]*width,p[2][1]*height); context.stroke();
        }
        context.restore();
    }
    }
})();
