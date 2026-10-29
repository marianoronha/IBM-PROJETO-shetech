"""
Repositório de perfis sintéticos de usuário.

Lê os dados de synthetic_users.json e synthetic_transactions.json.
Nunca expõe dados pessoais fora deste módulo — retorna apenas
estruturas de análise de comportamento (sem nome, sem número de conta).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename: str) -> list[dict]:
    path = _DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Cache em memória (dados sintéticos são estáticos no MVP)
_users: dict[str, dict] = {}
_transactions: list[dict] = []


def _ensure_loaded() -> None:
    global _users, _transactions
    if not _users:
        for u in _load_json("synthetic_users.json"):
            _users[u["user_id"]] = u
    if not _transactions:
        _transactions = _load_json("synthetic_transactions.json")


def get_user_profile(user_id: str) -> Optional[dict]:
    """Retorna o perfil sintético do usuário ou None se não encontrado."""
    _ensure_loaded()
    return _users.get(user_id)


def get_user_transactions(user_id: str) -> list[dict]:
    """Retorna histórico de transações do usuário (apenas campos de análise)."""
    _ensure_loaded()
    return [
        {
            "tx_id": t["tx_id"],
            "type": t["type"],
            "amount": t["amount"],
            "recipient": t["recipient"],
            "channel": t["channel"],
            "status": t["status"],
        }
        for t in _transactions
        if t["user_id"] == user_id
    ]


def get_pending_transaction(transaction_id: str) -> Optional[dict]:
    """Retorna uma transação pendente pelo ID."""
    _ensure_loaded()
    for t in _transactions:
        if t["tx_id"] == transaction_id:
            return t
    return None
