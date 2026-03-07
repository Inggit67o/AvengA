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


# ---------------------------------------------------------------------------
# REPORT BUILDERS
# ---------------------------------------------------------------------------

def build_draft_report(d: SignalDraft) -> str:
    return (
        f"asset={get_asset_class_label(d.asset_class)} "
        f"conviction={get_conviction_label(d.conviction_tier)} "
        f"size_wei={d.size_wei}"
    )


def build_session_report(session: AvengASession) -> str:
    lines = [f"=== {APP_NAME} Session — {HULK_TAGLINE} ===", ""]
    lines.append(f"Drafts: {len(session.drafts)}")
    for i, d in enumerate(session.drafts, 1):
        lines.append(f"  [{i}] {build_draft_report(d)}")
    lines.append("")
    lines.append(f"Records: {len(session.records)}")
    for r in session.records:
        avg = (r.vote_sum / r.vote_count) if r.vote_count else 0
        lines.append(
            f"  {r.signal_id[:18]}... creator={r.creator[:10]}... "
            f"ac={r.asset_class} ct={r.conviction_tier} smashed={r.smashed} votes={r.vote_count} avg={avg}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CONTRACT ABI STUB (HulkAI)
# ---------------------------------------------------------------------------

def abi_encode_register_signal(
    signal_id_hex: str,
    asset_class: int,
    conviction_tier: int,
    size_wei: int,
) -> Dict[str, Any]:
    return {
        "method": "registerSignal",
        "params": {
            "signalId": signal_id_hex,
            "assetClass": asset_class,
            "convictionTier": conviction_tier,
            "sizeWei": size_wei,
        },
    }


def abi_encode_smash_pick(signal_id_hex: str) -> Dict[str, Any]:
    return {"method": "smashPick", "params": {"signalId": signal_id_hex}}


def abi_encode_vote_conviction(
    signal_id_hex: str,
    score: int,
    fee_wei: int = 0,
) -> Dict[str, Any]:
    return {
        "method": "voteConviction",
        "params": {"signalId": signal_id_hex, "score": score},
        "valueWei": fee_wei,
    }


# ---------------------------------------------------------------------------
# GAS ESTIMATES (approximate)
# ---------------------------------------------------------------------------

GAS_REGISTER_SIGNAL = 280_000
GAS_SMASH_PICK = 85_000
GAS_VOTE_CONVICTION = 140_000
GAS_RETIRE_SIGNAL = 65_000


def get_gas_estimates() -> Dict[str, int]:
    return {
        "registerSignal": GAS_REGISTER_SIGNAL,
        "smashPick": GAS_SMASH_PICK,
        "voteConviction": GAS_VOTE_CONVICTION,
        "retireSignal": GAS_RETIRE_SIGNAL,
    }


# ---------------------------------------------------------------------------
# DEMO / DEFAULT DATA
# ---------------------------------------------------------------------------

def create_demo_draft() -> SignalDraft:
    return SignalDraft(
        asset_class=random.randint(0, min(3, HULK_MAX_ASSET_CLASS)),
        conviction_tier=random.randint(0, min(4, HULK_MAX_CONVICTION)),
        size_wei=random.randint(1e18, 10 * 1e18),
        notes="Demo Hulk Smash pick",
    )


def create_demo_session(num_drafts: int = 5) -> AvengASession:
    session = AvengASession()
    for _ in range(num_drafts):
        session.drafts.append(create_demo_draft())
    return session


def run_demo() -> None:
    session = create_demo_session()
    print(build_session_report(session))
    path = os.path.abspath("avenga_demo_session.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(session.to_json())
    print(f"\nDemo session saved to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_usage() -> None:
    print(f"{APP_NAME} v{APP_VERSION} — {HULK_TAGLINE}")
    print("Usage: python AvengA.py [--demo] [--help] [--version] [--gas]")
    print("  --demo   run demo and save avenga_demo_session.json")
    print("  --gas    print gas estimates for HulkAI")
    print("  --help   this message")
    print("  No args  interactive wizard (register drafts, show report)")


def main(args: List[str]) -> int:
    if "--help" in args or "-h" in args:
        print_usage()
        return 0
    if "--version" in args or "-v" in args:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--demo" in args:
        run_demo()
        return 0
    if "--gas" in args:
        for name, gas in get_gas_estimates().items():
            print(f"  {name}: {gas}")
        return 0

    session = AvengASession()
    print(f"Welcome to {APP_NAME} — {HULK_TAGLINE}\n")
    try:
        n = input("How many signal drafts to add? [3] ").strip() or "3"
        num = int(n)
    except ValueError:
        num = 3
    num = max(0, min(num, 20))
    for i in range(num):
        ac = random.randint(0, min(5, HULK_MAX_ASSET_CLASS))
        ct = random.randint(0, min(4, HULK_MAX_CONVICTION))
        size = random.randint(0, 5 * 10**18)
        session.drafts.append(SignalDraft(asset_class=ac, conviction_tier=ct, size_wei=size, notes=""))
    print(build_session_report(session))
    return 0


# ---------------------------------------------------------------------------
# ERROR CODES (HulkAI contract)
# ---------------------------------------------------------------------------

ERROR_CODES = {
    "HulkAI_NotOwner": "Caller is not owner",
    "HulkAI_NotGammaOracle": "Caller is not gamma oracle",
    "HulkAI_NotBannerGuardian": "Caller is not banner guardian",
    "HulkAI_ZeroAddress": "Zero address not allowed",
    "HulkAI_ZeroSignal": "Zero signal id not allowed",
    "HulkAI_AlreadyExists": "Signal already registered",
    "HulkAI_NotFound": "Signal not found or retired",
    "HulkAI_AlreadyRetired": "Signal already retired",
    "HulkAI_InvalidAssetClass": "Asset class out of range",
    "HulkAI_InvalidConviction": "Conviction tier out of range",
    "HulkAI_InvalidVoteScore": "Vote score must be 1..10",
    "HulkAI_Reentrant": "Reentrancy detected",
    "HulkAI_TooManySignals": "Max signals reached",
    "HulkAI_AlreadyVoted": "Caller already voted on this signal",
    "HulkAI_InvalidFeeBps": "Fee bps exceeds max",
    "HulkAI_NamespaceFrozen": "Namespace is frozen",
    "HulkAI_InsufficientFee": "Insufficient fee sent",
    "HulkAI_InvalidIndex": "Index out of range",
    "HulkAI_NotSmashed": "Signal is not smashed",
}


def get_error_description(code: str) -> str:
    return ERROR_CODES.get(code, "Unknown error")


def print_error_codes() -> None:
    for code, desc in ERROR_CODES.items():
        print(f"  {code}: {desc}")


# ---------------------------------------------------------------------------
# CONFIG / BOUNDS
# ---------------------------------------------------------------------------

DEFAULT_MIN_ASSET_CLASS = 0
DEFAULT_MAX_ASSET_CLASS = 12
DEFAULT_MIN_CONVICTION = 0
DEFAULT_MAX_CONVICTION = 7
DEFAULT_MIN_SIZE_WEI = 0
DEFAULT_MAX_SIZE_WEI = 10**24
MAX_DRAFTS_PER_SESSION = 64


def session_to_register_params(draft: SignalDraft, signal_id_hex: str) -> Dict[str, Any]:
    return {
        "signal_id": signal_id_hex,
        "asset_class": clamp_asset_class(draft.asset_class),
        "conviction_tier": clamp_conviction(draft.conviction_tier),
        "size_wei": max(0, draft.size_wei),
    }


# ---------------------------------------------------------------------------
# STATE ENCODE / DECODE
# ---------------------------------------------------------------------------

def encode_session_to_dict(session: AvengASession) -> Dict[str, Any]:
    return dataclasses.asdict(session)


def decode_session_from_dict(data: Dict[str, Any]) -> AvengASession:
    drafts: List[SignalDraft] = []
    for d in data.get("drafts", []):
        drafts.append(
            SignalDraft(
                asset_class=int(d.get("asset_class", 0)),
                conviction_tier=int(d.get("conviction_tier", 0)),
                size_wei=int(d.get("size_wei", 0)),
                notes=str(d.get("notes", "")),
            )
        )
    records: List[SignalRecord] = []
    for r in data.get("records", []):
        records.append(
            SignalRecord(
                signal_id=str(r.get("signal_id", "")),
                creator=str(r.get("creator", "")),
                asset_class=int(r.get("asset_class", 0)),
                conviction_tier=int(r.get("conviction_tier", 0)),
                size_wei=int(r.get("size_wei", 0)),
                created_at=int(r.get("created_at", 0)),
                smashed=bool(r.get("smashed", False)),
                retired=bool(r.get("retired", False)),
                vote_count=int(r.get("vote_count", 0)),
                vote_sum=int(r.get("vote_sum", 0)),
            )
        )
    return AvengASession(drafts=drafts, records=records, notes=str(data.get("notes", "")))


def load_session_from_file(path: str) -> AvengASession:
    with open(path, "r", encoding="utf-8") as f:
        return decode_session_from_dict(json.load(f))


def save_session_to_file(session: AvengASession, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(session.to_json())


# ---------------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------------

import csv as _csv


def export_drafts_to_csv(drafts: List[SignalDraft], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["asset_class", "conviction_tier", "size_wei", "notes"])
        for d in drafts:
            w.writerow([d.asset_class, d.conviction_tier, d.size_wei, (d.notes or "")[:200]])


def export_records_to_csv(records: List[SignalRecord], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(
            [
                "signal_id",
                "creator",
                "asset_class",
                "conviction_tier",
                "size_wei",
                "created_at",
                "smashed",
                "retired",
                "vote_count",
                "vote_sum",
            ]
        )
        for r in records:
            w.writerow(
                [
                    r.signal_id,
                    r.creator,
                    r.asset_class,
                    r.conviction_tier,
                    r.size_wei,
                    r.created_at,
                    r.smashed,
                    r.retired,
                    r.vote_count,
                    r.vote_sum,
                ]
            )


# ---------------------------------------------------------------------------
# RUNBOOK
# ---------------------------------------------------------------------------

RUNBOOK_STEPS = [
    "1. Create signal drafts (asset class, conviction tier, size_wei).",
    "2. Derive signal IDs (creator + nonce + salt).",
    "3. Submit registerSignal to HulkAI (or use AvengA CLI / web3).",
    "4. Gamma oracle can smashPick to approve; guardian can retireSignal.",
    "5. Anyone can voteConviction once per signal (1..10) with optional fee.",
]


def get_runbook() -> List[str]:
    return list(RUNBOOK_STEPS)


def print_runbook() -> None:
    for step in RUNBOOK_STEPS:
        print(step)


# ---------------------------------------------------------------------------
# BATCH HELPERS
# ---------------------------------------------------------------------------

def build_drafts_batch(
    num: int,
    asset_class_range: Tuple[int, int] = (0, 5),
    conviction_range: Tuple[int, int] = (0, 5),
    size_min: int = 0,
    size_max: int = 5 * 10**18,
) -> List[SignalDraft]:
    drafts: List[SignalDraft] = []
    for _ in range(min(num, MAX_DRAFTS_PER_SESSION)):
        ac = random.randint(asset_class_range[0], min(asset_class_range[1], HULK_MAX_ASSET_CLASS))
        ct = random.randint(conviction_range[0], min(conviction_range[1], HULK_MAX_CONVICTION))
        size = random.randint(size_min, size_max) if size_max > size_min else size_min
        drafts.append(SignalDraft(asset_class=ac, conviction_tier=ct, size_wei=size, notes=""))
    return drafts


def build_session_from_dicts(
    drafts_data: List[Dict[str, Any]],
    records_data: Optional[List[Dict[str, Any]]] = None,
) -> AvengASession:
    drafts: List[SignalDraft] = []
    for d in drafts_data:
        drafts.append(
            SignalDraft(
                asset_class=int(d.get("asset_class", 0)),
                conviction_tier=int(d.get("conviction_tier", 0)),
                size_wei=int(d.get("size_wei", 0)),
                notes=str(d.get("notes", "")),
            )
        )
    records: List[SignalRecord] = []
    for r in (records_data or []):
        records.append(
            SignalRecord(
                signal_id=str(r.get("signal_id", "")),
                creator=str(r.get("creator", "")),
                asset_class=int(r.get("asset_class", 0)),
                conviction_tier=int(r.get("conviction_tier", 0)),
                size_wei=int(r.get("size_wei", 0)),
                created_at=int(r.get("created_at", 0)),
                smashed=bool(r.get("smashed", False)),
                retired=bool(r.get("retired", False)),
                vote_count=int(r.get("vote_count", 0)),
                vote_sum=int(r.get("vote_sum", 0)),
            )
        )
    return AvengASession(drafts=drafts, records=records)


# ---------------------------------------------------------------------------
# FEE CALCULATION
# ---------------------------------------------------------------------------

def required_fee_wei(value_wei: int, fee_bps: int = 50) -> int:
    return (value_wei * fee_bps) // HULK_FEE_DENOM_BPS


def refund_wei(value_wei: int, fee_bps: int = 50) -> int:
    return value_wei - required_fee_wei(value_wei, fee_bps)


def quote_fee_for_amount(amount_wei: int, fee_bps: int = 50) -> int:
    return (amount_wei * fee_bps) // HULK_FEE_DENOM_BPS


# ---------------------------------------------------------------------------
# STRING / DISPLAY
# ---------------------------------------------------------------------------

def format_draft_one_line(d: SignalDraft) -> str:
    return f"{get_asset_class_label(d.asset_class)} ct={d.conviction_tier} size={d.size_wei}"


def format_record_one_line(r: SignalRecord) -> str:
    avg = (r.vote_sum / r.vote_count) if r.vote_count else 0
    return f"{r.signal_id[:16]}... ac={r.asset_class} smashed={r.smashed} votes={r.vote_count} avg={avg}"


def drafts_to_markdown(drafts: List[SignalDraft]) -> str:
    lines = ["## Signal drafts", ""]
    for i, d in enumerate(drafts, 1):
        lines.append(f"{i}. **{get_asset_class_label(d.asset_class)}** conviction {get_conviction_label(d.conviction_tier)} size_wei={d.size_wei}")
    return "\n".join(lines)


def session_to_markdown(session: AvengASession) -> str:
