#!/usr/bin/env python3
"""
AvengA — Hulk Smash client for the HulkAI on-chain signal registry.

Superhero AI for crypto investing: register signals (asset class, conviction tier, size),
submit to HulkAI, and vote conviction. Use as CLI wizard or library. Optional web3 stub
to interact with the HulkAI contract.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


APP_NAME = "AvengA"
APP_VERSION = "1.0.0"
HULK_TAGLINE = "Hulk Smash"


# ---------------------------------------------------------------------------
# CONSTANTS (match HulkAI.sol)
# ---------------------------------------------------------------------------

HULK_MAX_ASSET_CLASS = 12
HULK_MAX_CONVICTION = 7
HULK_MAX_VOTE_SCORE = 10
HULK_MIN_VOTE_SCORE = 1
HULK_MAX_FEE_BPS = 500
HULK_FEE_DENOM_BPS = 10_000

ASSET_CLASS_LABELS = [
    "btc",
    "eth",
    "l2",
    "defi",
    "meme",
    "ai",
    "rwa",
    "gaming",
    "infra",
    "privacy",
    "stable",
    "other",
]

CONVICTION_TIER_LABELS = [
    "watch",
    "dip-buy",
    "accumulate",
    "hold",
    "strong-hold",
    "max-conviction",
    "experimental",
]


@dataclass
class SignalDraft:
    """Off-chain draft for a HulkAI signal."""
    asset_class: int
    conviction_tier: int
    size_wei: int
    notes: str = ""


@dataclass
class SignalRecord:
    """Mirror of on-chain signal record (read-only view)."""
    signal_id: str
    creator: str
    asset_class: int
    conviction_tier: int
    size_wei: int
    created_at: int
    smashed: bool
    retired: bool
    vote_count: int = 0
    vote_sum: int = 0


@dataclass
class AvengASession:
    """Session holding drafts and optional fetched records."""
    drafts: List[SignalDraft] = field(default_factory=list)
    records: List[SignalRecord] = field(default_factory=list)
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)


# ---------------------------------------------------------------------------
# SIGNAL ID DERIVATION
# ---------------------------------------------------------------------------

def derive_signal_id(creator_hex: str, nonce: int, salt_hex: str) -> str:
    """Compute keccak256(creator || nonce || salt) as hex."""
    payload = creator_hex.lower().strip().replace("0x", "") + f"{nonce:x}" + salt_hex.replace("0x", "")
    if len(payload) % 2:
        payload = "0" + payload
    data = bytes.fromhex(payload)
    h = hashlib.sha3_256(data)
    return "0x" + h.hexdigest()


def derive_signal_id_bytes32(creator_hex: str, nonce: int, salt_hex: str) -> bytes:
    """Return 32-byte signal id for ABI encoding."""
    payload = creator_hex.lower().strip().replace("0x", "") + f"{nonce:x}" + salt_hex.replace("0x", "")
    if len(payload) % 2:
        payload = "0" + payload
    data = bytes.fromhex(payload)
    return hashlib.sha3_256(data).digest()


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_draft(d: SignalDraft) -> List[str]:
    errs: List[str] = []
    if d.asset_class < 0 or d.asset_class > HULK_MAX_ASSET_CLASS:
        errs.append(f"asset_class must be 0..{HULK_MAX_ASSET_CLASS}")
    if d.conviction_tier < 0 or d.conviction_tier > HULK_MAX_CONVICTION:
        errs.append(f"conviction_tier must be 0..{HULK_MAX_CONVICTION}")
    if d.size_wei < 0:
        errs.append("size_wei must be non-negative")
    return errs


def validate_vote_score(score: int) -> List[str]:
    if score < HULK_MIN_VOTE_SCORE or score > HULK_MAX_VOTE_SCORE:
        return [f"score must be {HULK_MIN_VOTE_SCORE}..{HULK_MAX_VOTE_SCORE}"]
    return []


def clamp_asset_class(i: int) -> int:
    return max(0, min(HULK_MAX_ASSET_CLASS, i))


def clamp_conviction(i: int) -> int:
    return max(0, min(HULK_MAX_CONVICTION, i))


def clamp_vote_score(s: int) -> int:
    return max(HULK_MIN_VOTE_SCORE, min(HULK_MAX_VOTE_SCORE, s))


# ---------------------------------------------------------------------------
# LABELS
# ---------------------------------------------------------------------------

def get_asset_class_label(i: int) -> str:
    if 0 <= i < len(ASSET_CLASS_LABELS):
        return ASSET_CLASS_LABELS[i]
    return "unknown"


def get_conviction_label(i: int) -> str:
    if 0 <= i < len(CONVICTION_TIER_LABELS):
        return CONVICTION_TIER_LABELS[i]
    return "unknown"


