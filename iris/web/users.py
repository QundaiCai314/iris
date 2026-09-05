# -*- coding: utf-8 -*-
"""M8 用户与数据管理：本地账号体系（JSON 文件存储）+ 登录令牌 + 我的数据。

设计（单机 demo，产品化时换数据库即可）：
- 存储：data/users/<用户名>.json；写盘原子（tmp + os.replace）；
- 密码：pbkdf2_hmac(sha256) 加盐 20 万轮，不落明文；
- 令牌：内存表 token -> username（重启失效），前端 localStorage 保存；
- 数据：决策历史（完整卡片快照）/ 关注清单 / 分品类画像答案；支持导出与注销。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(WEB_DIR))          # F:/Iris
USER_DIR = os.path.join(ROOT, "data", "users")            # 可被测试 monkeypatch

USERNAME_RE = re.compile("^[A-Za-z0-9_\u4e00-\u9fa5-]{2,20}$")
PBKDF2_ROUNDS = 200_000
TOKEN_TTL_SEC = 7 * 24 * 3600
MIN_PASSWORD = 6

_tokens: Dict[str, dict] = {}                             # token -> {user, created}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path(username: str) -> str:
    return os.path.join(USER_DIR, username + ".json")


# ---------- 底层 IO ----------

def _ensure_dir() -> None:
    os.makedirs(USER_DIR, exist_ok=True)


def _read(username: str) -> Optional[dict]:
    p = _path(username)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(username: str, data: dict) -> None:
    _ensure_dir()
    fd, tmp = tempfile.mkstemp(dir=USER_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path(username))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def exists(username: str) -> bool:
    return os.path.exists(_path(username))


# ---------- 密码 / 令牌 ----------

def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt, PBKDF2_ROUNDS).hex()


def validate_username(username: str) -> Optional[str]:
    if not username or not USERNAME_RE.match(username):
        return "用户名需 2-20 位中文/字母/数字/下划线"
    return None


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < MIN_PASSWORD:
        return "密码至少 %d 位" % MIN_PASSWORD
    return None


def register(username: str, password: str) -> dict:
    uerr = validate_username(username)
    if uerr:
        raise ValueError(uerr)
    perr = validate_password(password)
    if perr:
        raise ValueError(perr)
    salt = secrets.token_bytes(16)
    doc = {
        "username": username,
        "salt": salt.hex(),
        "password_hash": _hash_password(password, salt),
        "created_at": _now(),
        "cards": [],
        "watchlist": [],
        "profiles": {},          # category -> {answers, at}
    }
    if exists(username):
        raise ValueError("用户名已存在，换一个或直接登录")
    _write(username, doc)
    return doc


def verify_login(username: str, password: str) -> bool:
    doc = _read(username)
    if not doc:
        return False
    salt = bytes.fromhex(doc["salt"])
    return hmac.compare_digest(doc["password_hash"],
                               _hash_password(password, salt))


def _prune_tokens() -> None:
    now = time.time()
    for tok, v in list(_tokens.items()):
        if now - v["created"] > TOKEN_TTL_SEC:
            _tokens.pop(tok, None)


def issue_token(username: str) -> str:
    _prune_tokens()
    tok = secrets.token_urlsafe(24)
    _tokens[tok] = {"user": username, "created": time.time()}
    return tok


def user_for_token(token: str) -> Optional[str]:
    if not token:
        return None
    v = _tokens.get(token)
    if not v:
        return None
    if time.time() - v["created"] > TOKEN_TTL_SEC:
        _tokens.pop(token, None)
        return None
    return v["user"]


def revoke_token(token: str) -> None:
    _tokens.pop(token, None)


def revoke_user_tokens(username: str) -> None:
    for tok, v in list(_tokens.items()):
        if v["user"] == username:
            _tokens.pop(tok, None)


# ---------- 决策历史（完整卡片快照） ----------

def add_card(username: str, product: dict, sku_id: Optional[str],
             profile: dict, card: Optional[dict], note: str = "") -> dict:
    doc = _read(username)
    if doc is None:
        raise KeyError("用户不存在")
    entry = {
        "id": uuid.uuid4().hex[:12],
        "at": _now(),
        "kind": "card" if card else "no_data",
        "product": product,
        "sku_id": sku_id,
        "profile": profile,
        "snapshot": card,
        "note": note,
    }
    doc["cards"].append(entry)
    _write(username, doc)
    return entry


def list_cards(username: str) -> List[dict]:
    doc = _read(username) or {}
    out = []
    for e in reversed(doc.get("cards", [])):
        d = (e.get("snapshot") or {}).get("decision") or {}
        out.append({
            "id": e["id"], "at": e["at"], "kind": e["kind"],
            "product": e.get("product") or {}, "sku_id": e.get("sku_id"),
            "recommendation": d.get("recommendation"),
            "traffic_light": d.get("traffic_light"),
            "p2": (d.get("p2") or {}).get("probability"),
            "note": e.get("note", ""),
        })
    return out


def get_card(username: str, card_id: str) -> Optional[dict]:
    doc = _read(username) or {}
    for e in doc.get("cards", []):
        if e["id"] == card_id:
            return e
    return None


def delete_card(username: str, card_id: str) -> bool:
    doc = _read(username)
    if doc is None:
        return False
    before = len(doc.get("cards", []))
    doc["cards"] = [e for e in doc["cards"] if e["id"] != card_id]
    if len(doc["cards"]) == before:
        return False
    _write(username, doc)
    return True


# ---------- 关注清单 ----------

def _watch_exists(doc: dict, sku_id: str) -> bool:
    return any(w.get("sku_id") == sku_id for w in doc.get("watchlist", []))


def set_watch(username: str, sku_id: str) -> dict:
    doc = _read(username)
    if doc is None:
        raise KeyError("用户不存在")
    if not _watch_exists(doc, sku_id):
        doc["watchlist"].append({"sku_id": sku_id, "at": _now()})
        _write(username, doc)
    return {"sku_id": sku_id, "watching": True}


def remove_watch(username: str, sku_id: str) -> bool:
    doc = _read(username)
    if doc is None:
        return False
    before = len(doc.get("watchlist", []))
    doc["watchlist"] = [w for w in doc["watchlist"] if w.get("sku_id") != sku_id]
    if len(doc["watchlist"]) == before:
        return False
    _write(username, doc)
    return True


def list_watch(username: str) -> List[dict]:
    doc = _read(username) or {}
    return list(reversed(doc.get("watchlist", [])))


# ---------- 画像答案（分品类预填） ----------

def save_answers(username: str, category: str, answers: Dict) -> None:
    doc = _read(username)
    if doc is None:
        raise KeyError("用户不存在")
    doc["profiles"][category] = {"answers": dict(answers or {}),
                                 "at": _now()}
    _write(username, doc)


def get_answers(username: str, category: str) -> Optional[dict]:
    doc = _read(username) or {}
    p = (doc.get("profiles") or {}).get(category)
    return p["answers"] if p else None




def info(username: str) -> Optional[dict]:
    """账号概览（/api/me 用）。"""
    doc = _read(username)
    if doc is None:
        return None
    return {"username": doc.get("username"),
            "created_at": doc.get("created_at"),
            "stats": {"cards": len(doc.get("cards", [])),
                      "watch": len(doc.get("watchlist", [])),
                      "profiles": len(doc.get("profiles", {}))}}

# ---------- 导出 / 注销 ----------

def export_user(username: str) -> dict:
    doc = _read(username)
    if doc is None:
        raise KeyError("用户不存在")
    return {"exported_at": _now(), "app": "iris",
            "username": doc.get("username"),
            "created_at": doc.get("created_at"),
            "profiles": doc.get("profiles", {}),
            "watchlist": doc.get("watchlist", []),
            "cards": list(reversed(doc.get("cards", [])))}


def delete_user(username: str) -> bool:
    if not os.path.exists(_path(username)):
        return False
    os.remove(_path(username))
    revoke_user_tokens(username)
    return True
