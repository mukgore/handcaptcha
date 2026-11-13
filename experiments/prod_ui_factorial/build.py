"""Build a local research UI from the production document; keep root prod intact."""
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FACTORS=('selection','overlay','copy','compare','guide','reveal')


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Production hook changed: '+old[:55])
    return text.replace(old,new)


def build():
    original=(ROOT/'hand_captcha_prod.html').read_text(encoding='utf8')
    source=original
    source=re.sub(r'    <script src="https://unpkg.com/[^\n]+</script>\n','',source)
    source=re.sub(r'    <link href="https://fonts.googleapis.com/[^\n]+\n','',source)
    head='''<base href="../../">
<link rel="stylesheet" href="experiments/prod_palm_variants/guidance.css">
<link rel="stylesheet" href="experiments/prod_ui_factorial/study.css">
<script src="experiments/prod_ui_factorial/conditions.js"></script>
<script>const UI_FACTORS=UIFactorial.fromSearch(location.search);let uiPreludeBlocked=false;</script>
'''
    source=once(source,'</head>',head+'</head>')
    # Local selected files replace public pool fetches for every condition.
    source=once(source,"const POOL_BASE = 'https://mukgore.github.io/handcaptcha/';","const POOL_BASE = ''; // local research files only")
    if "const UPLOAD_URL = '';" not in source or 'const SAVE_LOCAL_JSON = false;' not in source:
        raise ValueError('Research UI requires disabled automatic upload/download')
    source=once(source,'maxNumHands:1','maxNumHands:UI_FACTORS.selection ? 2 : 1')
    source=once(source,'hands.onResults(onRes);','hands.onResults(result => onRes(result));')
    source=once(source,'genSequence().then(startRealChallenge);','genSequence().then(() => { if(!selectionRunAborted) startRealChallenge(); });')
    source=once(source,'let selectedHand = null;','let selectionRunAborted=false, selectionRunFinished=false;\nlet selectedHand = null;')
    source=once(source,'cv.srcObject = camStream; await cv.play();',
        'if(selectionRunAborted){camStream.getTracks().forEach(t=>t.stop());return;}\ncv.srcObject = camStream; await cv.play();\nif(selectionRunAborted){camStream.getTracks().forEach(t=>t.stop());return;}')
    source=once(source,'await initMP();\n    await loadPoolManifest();',
        'await initMP();\n    if(selectionRunAborted)return;\n    await loadPoolManifest();\n    if(selectionRunAborted)return;')
    source=once(source,'(async function loop(){ if(cv.readyState>=2) await hands.send({image:cv}); animId = requestAnimationFrame(loop); })();',
        '(async function loop(){if(selectionRunAborted||selectionRunFinished)return;if(cv.readyState>=2)await hands.send({image:cv});if(!selectionRunAborted&&!selectionRunFinished)animId=requestAnimationFrame(loop);})();')
    source=once(source,"version: 'prod_v2_pool'","version: 'prod_ui_factorial_v1'")
    # One source per diagnostic trial: do not pretend the existing single original is two independent clips.
    source=once(source,'if(candidates.length < 2)','if(candidates.length < 1)')
    source=once(source,'if(usedClips >= 2) break;','if(usedClips >= 1) break;')
    source=once(source,'if(usedClips < 2)','if(usedClips < 1)')
    source=source.replace('(need >= 2)','(need >= 1)').replace('(need 2)','(need 1)')
    source=once(source,'const shuffled = [...candidates].sort(() => Math.random()-0.5);','const shuffled = [...candidates]; // fixed local source across UI conditions')
    source=once(source,'\nbootstrap();','\n/* local study setup starts bootstrap after paired input checks */')
    source=once(source,'setTimeout(dismissIntroBanner, 8000);','/* Intro timer starts with the research trial. */')
    source=once(source,'setTimeout(() => location.reload(), 3000);','/* Research result remains until explicit restart/export. */')
    bridge=(ROOT/'experiments/prod_selected_hand/bridge.js').read_text(encoding='utf8')
    if '</script' in bridge.lower():raise ValueError('Unsafe embedded bridge text')
    tail='''<script>
const uiNativeOnRes=onRes;
onRes=function(result){if(uiPreludeBlocked)UIStudy.drawCameraOnly(result);else uiNativeOnRes(result);};
</script>
<script src="experiments/hand_selection/selection.js"></script>
<script>if(UI_FACTORS.selection){
'''+bridge+'''
}</script>
<script src="experiments/prod_ui_factorial/study.js"></script>
'''
    source=once(source,'</body>',tail+'</body>')
    source=source.replace('<body>','<body class="factorial-study">',1)
    (HERE/'run.html').write_text(source,encoding='utf8',newline='\n')
    matrix=[{'condition_id':f'ui-{mask:02d}','mask':mask,
             **{name:bool(mask&(1<<i)) for i,name in enumerate(FACTORS)}} for mask in range(64)]
    design={'schema_version':1,'scope':'complete_factorial_design_not_observations',
        'production_source_normalized_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'factors':list(FACTORS),'conditions':matrix,'hold_ms':500,'fade_ms':500,
        'common_prelude_ms':1000,'human_effects_verified':False}
    (HERE/'design.json').write_text(json.dumps(design,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Built prod-derived UI and all 64 conditions; no raw media included')


if __name__=='__main__':build()
