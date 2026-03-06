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
