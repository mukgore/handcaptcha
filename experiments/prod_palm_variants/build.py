"""Produce additive UI variants from the current, unmodified production HTML."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
VARIANTS = {'a_copy': 'copy', 'b_compare': 'compare', 'c_guide': 'guide'}


def render(source, variant):
    if variant not in VARIANTS.values():
        raise ValueError('Unknown UI variant')
    if source.count('</head>') != 1 or source.count('</body>') != 1:
        raise ValueError('Expected a single production document')
    sha = hashlib.sha256(source.encode('utf8')).hexdigest()
    head = ('<base href="../../">\n'
            '<link rel="stylesheet" href="experiments/prod_palm_variants/guidance.css">\n'
            f'<!-- Generated from hand_captcha_prod.html; normalized UTF-8 SHA256 {sha} -->\n')
    tail = (f'<script src="experiments/prod_palm_variants/guidance.js" data-palm-variant="{variant}"></script>\n')
    return source.replace('</head>', head + '</head>').replace('</body>', tail + '</body>')


def main():
    source = (ROOT / 'hand_captcha_prod.html').read_text(encoding='utf8')
    for name, variant in VARIANTS.items():
        (OUT / f'{name}.html').write_text(render(source, variant), encoding='utf8', newline='\n')
    print('Built 3 variants from unchanged hand_captcha_prod.html')


if __name__ == '__main__':
    main()
