# -*- coding: utf-8 -*-
"""M3.3 门控测试。"""
from datetime import date

from iris.core.gate import SUPPLY_LOOKBACK_DAYS, check_gate, recent_supply
from iris.core.models import EventItem


def _ev(eid, typ, title, dt, scope="rtx5080"):
    return EventItem(eid, typ, title, dt, scope, "reported")


def test_recent_supply_found():
    evs = [_ev("s1", "supply", "缺货", "2026-07-01", "rtx5080")]
    s = recent_supply(evs, "rtx5080", date(2026, 8, 1))
    assert s is not None


def test_recent_supply_outside_window():
    evs = [_ev("s1", "supply", "缺货", "2026-01-01", "rtx5080")]
    s = recent_supply(evs, "rtx5080", date(2026, 8, 1))
    assert s is None


def test_supply_future_not_counted():
    evs = [_ev("s1", "supply", "缺货", "2026-12-01", "rtx5080")]
    s = recent_supply(evs, "rtx5080", date(2026, 8, 1))
    assert s is None


def test_supply_scope_mismatch():
    evs = [_ev("s1", "supply", "缺货", "2026-07-01", "rtx5070")]
    s = recent_supply(evs, "rtx5080", date(2026, 8, 1))
    assert s is None


def test_gate_vol_trigger():
    evs = []
    g = check_gate(0.95, evs, "rtx5080", date(2026, 8, 1))
    assert g["abnormal"] is True and len(g["reasons"]) == 1


def test_gate_quiet():
    evs = []
    g = check_gate(0.5, evs, "rtx5080", date(2026, 8, 1))
    assert g["abnormal"] is False and g["reasons"] == []


def test_gate_supply_trigger():
    evs = [_ev("s1", "supply", "缺货", "2026-07-20", "rtx5080")]
    g = check_gate(0.3, evs, "rtx5080", date(2026, 8, 1))
    assert g["abnormal"] is True
    assert any("供需" in x for x in g["reasons"])
