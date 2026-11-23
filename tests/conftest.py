import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


def dino_path():
    """The DinoLight board (github.com/mo-seph/dino-board) is the reference design for the
    fault-injection tests.  It is not vendored: point BOARDLINT_DINO at a checkout."""
    # the fault list names reference designators of commit 4da182c
    for p in (os.environ.get('BOARDLINT_DINO'), os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'dino-board-4da182c')):
        if p and os.path.exists(os.path.join(p, 'dinolight.kicad_sch')):
            return os.path.abspath(p)
    return None


@pytest.fixture(scope='session')
def ecp5():
    """https://github.com/mattvenn/basic-ecp5-pcb (KiCad 5): point BOARDLINT_ECP5 at its hardware/ directory."""
    for p in (os.environ.get('BOARDLINT_ECP5'),
              os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'ecp5', 'basic-ecp5-pcb', 'hardware')):
        if p and os.path.exists(os.path.join(p, 'basic-ecp5-pcb.kicad_pcb')):
            return os.path.abspath(p)
    pytest.skip('set BOARDLINT_ECP5 to the hardware/ directory of mattvenn/basic-ecp5-pcb')


@pytest.fixture(scope='session')
def dino():
    p = dino_path()
    if not p:
        pytest.skip('set BOARDLINT_DINO to a checkout of mo-seph/dino-board')
    return p
