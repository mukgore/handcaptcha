"""Run unittest classes AND the repository's legacy no-argument test functions."""
import importlib
import inspect
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
tests=ROOT/'dataset_pipeline'/'tests'
suite=unittest.defaultTestLoader.discover(str(tests))
functions=[]
for path in sorted(tests.glob('test_*.py')):
    module=importlib.import_module(path.stem)
    for name, value in inspect.getmembers(module, inspect.isfunction):
        if name.startswith('test_') and value.__module__==module.__name__:
            if inspect.signature(value).parameters:
                raise ValueError('Legacy function requires unsupported fixtures: '+name)
            functions.append(unittest.FunctionTestCase(value))
suite.addTests(functions)
print(f'Included legacy function tests: {len(functions)}',flush=True)
sys.exit(0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1)
