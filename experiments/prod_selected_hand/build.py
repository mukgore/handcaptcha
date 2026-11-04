"""Build an opt-in selection integration on the existing prod B UI."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Production hook changed: ' + old[:60])
    return text.replace(old, new)


def build():
    source = (ROOT / 'experiments/prod_palm_variants/b_compare.html').read_text(encoding='utf8')
    source = once(source, 'maxNumHands:1', 'maxNumHands:2')
    source = once(source, 'hands.onResults(onRes);', 'hands.onResults(result => onRes(result));')
    source = once(source, 'genSequence().then(startRealChallenge);',
                  'genSequence().then(() => { if(!selectionRunAborted) startRealChallenge(); });')
    source = once(source, "let selectedHand = null;", "let selectionRunAborted = false;\nlet selectionRunFinished = false;\nlet selectedHand = null;")
    source = once(source, 'cv.srcObject = camStream; await cv.play();',
                  'if(selectionRunAborted){camStream.getTracks().forEach(t=>t.stop());return;}\n        cv.srcObject = camStream; await cv.play();\n        if(selectionRunAborted){camStream.getTracks().forEach(t=>t.stop());return;}')
    source = once(source, '(async function loop(){ if(cv.readyState>=2) await hands.send({image:cv}); animId = requestAnimationFrame(loop); })();',
                  '(async function loop(){ if(selectionRunAborted || selectionRunFinished)return; if(cv.readyState>=2) await hands.send({image:cv}); if(!selectionRunAborted && !selectionRunFinished)animId = requestAnimationFrame(loop); })();')
    source = once(source, "version: 'prod_v2_pool'", "version: 'prod_selected_hand_experiment_v1'")
    source = once(source, 'await initMP();\n    await loadPoolManifest();',
                  'await initMP();\n    if(selectionRunAborted)return;\n    await loadPoolManifest();\n    if(selectionRunAborted)return;')
    source = once(source, '\nbootstrap();', '\n/* bootstrap follows selection integration */')
    additions = '''<script src="experiments/hand_selection/selection.js"></script>
<script src="experiments/prod_selected_hand/bridge.js"></script>
<script>bootstrap();</script>
'''
    source = once(source, '</body>', additions + '</body>')
    (HERE / 'index.html').write_text(source, encoding='utf8', newline='\n')


if __name__ == '__main__':
    build()
