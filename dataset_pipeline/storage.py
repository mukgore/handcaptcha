"""Keep private source/reference/candidates outside the static web root."""
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]


def private_output(path):
    resolved = Path(path).resolve()
    if resolved.is_relative_to(WEB_ROOT) or WEB_ROOT.is_relative_to(resolved):
        raise ValueError('Private outputs must be outside the static repository web root')
    return resolved
