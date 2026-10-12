# -*- coding: utf-8 -*-
"""快速运行全量测试套件（绕过全局 Python 环境的缓慢 plugin 扫描，毫秒级直接执行）。"""
import importlib
import inspect
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_FILES = [
    "test_smoke",
    "test_stats",
    "test_p1",
    "test_events",
    "test_calib",
    "test_alternatives",
    "test_decision",
    "test_card",
    "test_needs",
    "test_gate",
    "test_behavior",
    "test_pipeline",
    "test_lifecycle",
    "test_backtest",
    "test_prices",
    "test_llm",
    "test_econometrics",
]


class SimpleMonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value):
        orig = getattr(target, name)
        self._undo.append((target, name, orig))
        setattr(target, name, value)

    def delenv(self, name, raising=True):
        if name in os.environ:
            val = os.environ.pop(name)
            self._undo.append(("env", name, val))

    def setenv(self, name, value):
        orig = os.environ.get(name)
        self._undo.append(("env", name, orig))
        os.environ[name] = value

    def undo(self):
        for item in reversed(self._undo):
            if item[0] == "env":
                if item[2] is None:
                    os.environ.pop(item[1], None)
                else:
                    os.environ[item[1]] = item[2]
            else:
                setattr(item[0], item[1], item[2])


def main():
    t0 = time.time()
    total_passed = 0
    total_failed = 0
    failures = []

    for name in TEST_FILES:
        mod = importlib.import_module("tests." + name)
        test_funcs = [fn for fn in dir(mod) if fn.startswith("test_") and callable(getattr(mod, fn))]
        for fn_name in test_funcs:
            fn = getattr(mod, fn_name)
            sig = inspect.signature(fn)
            params = sig.parameters
            kwargs = {}
            temp_dirs = []
            mps = []
            if "tmp_path" in params:
                td = tempfile.mkdtemp()
                temp_dirs.append(td)
                kwargs["tmp_path"] = Path(td)
            if "monkeypatch" in params:
                mp = SimpleMonkeyPatch()
                mps.append(mp)
                kwargs["monkeypatch"] = mp

            try:
                fn(**kwargs)
                total_passed += 1
            except Exception as e:
                total_failed += 1
                failures.append((name, fn_name, str(e)))
                print(f"FAILED: {name}.{fn_name}: {e}")
            finally:
                for mp in mps:
                    mp.undo()
                for td in temp_dirs:
                    shutil.rmtree(td, ignore_errors=True)

    dt = time.time() - t0
    print("=" * 60)
    print(f"测试执行完成: {total_passed} 通过, {total_failed} 失败, 耗时 {dt:.2f}秒")
    print("=" * 60)
    if failures:
        print("\n失败用例列表:")
        for mod_name, fn_name, err in failures:
            print(f"  - {mod_name}.{fn_name}: {err}")
        sys.exit(1)
    else:
        print(f"ALL {total_passed} TESTS PASSED SUCCESSFULLY! ✓")


if __name__ == "__main__":
    main()
