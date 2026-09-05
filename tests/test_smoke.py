from iris import __version__
from iris.core.util import clamp, pct_change

def test_version():
    assert __version__ == "0.1.0"

def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10

def test_pct_change():
    assert pct_change(110, 100) == 0.1
    assert pct_change(100, 0) is None
