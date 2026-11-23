import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


def dino_path():
    """The DinoLight board (github.com/mo-seph/dino-board) is the reference design for the
    fault-injection tests.  It is not vendored: point BOARDLINT_DINO at a checkout."""
    for p in (os.environ.get('BOARDLINT_DINO'), os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'dino-board')):
        if p and os.path.exists(os.path.join(p, 'dinolight.kicad_sch')):
            return os.path.abspath(p)
    return None


@pytest.fixture(scope='session')
def dino():
    p = dino_path()
    if not p:
        pytest.skip('set BOARDLINT_DINO to a checkout of mo-seph/dino-board')
    return p
