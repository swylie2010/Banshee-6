"""
banshee_gateway.py — MCP behavioral contract + audit layer.

Every MCP tool call routes through BansheeGateway.call():
  1. Validates params against the tool's Pydantic schema
  2. Writes a structured audit entry to ~/.banshee_audit.jsonl
  3. Attaches _audit metadata to the response
  4. Returns the enriched response string

Schemas live here alongside the gateway class — one model per tool.
"""

import datetime
import json
import pathlib
import secrets
import time
from typing import Callable, Optional, Type

from pydantic import BaseModel, Field, field_validator

_AUDIT_PATH = pathlib.Path.home() / ".banshee_audit.jsonl"

VALID_MODES = ["long_term", "swing", "sniper", "active", "position"]
VALID_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]


# ── Per-tool schemas ──────────────────────────────────────────────────────────


class RadarSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    mode: str = Field("swing")
    output_mode: str = Field("human")

    @field_validator("mode")
    @classmethod
    def _mode(cls, v):
        if v not in VALID_MODES:
            raise ValueError(f"must be one of {VALID_MODES}")
        return v

    @field_validator("output_mode")
    @classmethod
    def _om(cls, v):
        if v not in ["human", "agent"]:
            raise ValueError("must be human or agent")
        return v


class ScanSchema(BaseModel):
    symbols: list = Field(..., min_length=1)
    mode: str = Field("swing")
    output_mode: str = Field("human")

    @field_validator("mode")
    @classmethod
    def _mode(cls, v):
        if v not in VALID_MODES:
            raise ValueError(f"must be one of {VALID_MODES}")
        return v


class NexusSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    mode: str = Field("swing")
    use_ai: bool = Field(True)
    output_mode: str = Field("human")

    @field_validator("mode")
    @classmethod
    def _mode(cls, v):
        if v not in VALID_MODES:
            raise ValueError(f"must be one of {VALID_MODES}")
        return v


class ExecutionPlanSchema(BaseModel):
    account_size: float = Field(..., gt=0)
    risk_percent: float = Field(..., gt=0, le=100)
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    smc_conflicted: bool = Field(False)


class StrategyResultsSchema(BaseModel):
    strategy_name: str = Field("")


class SMCSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    ltf: str = Field("4h")
    htf: str = Field("1d")
    use_ai: bool = Field(True)

    @field_validator("ltf", "htf")
    @classmethod
    def _tf(cls, v):
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"must be one of {VALID_TIMEFRAMES}")
        return v


class PaperTradeSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str
    entry_price: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    position_usd: float = Field(5000.0, gt=0)
    verdict: str = Field("")
    regime: str = Field("")
    macro_regime: str = Field("")
    notes: str = Field("")

    @field_validator("direction")
    @classmethod
    def _dir(cls, v):
        if v.upper() not in ["LONG", "SHORT"]:
            raise ValueError("must be LONG or SHORT")
        return v.upper()


class SignalOutcomeSchema(BaseModel):
    trade_id: int
    exit_reason: str = Field("")
    signal_correct: Optional[bool] = Field(None)
    note: str = Field("")


class OptionsCandidateSchema(BaseModel):
    account_size: Optional[float] = Field(None)

    @field_validator("account_size", mode="before")
    @classmethod
    def _acct(cls, v):
        if v is not None and v <= 0:
            raise ValueError("account_size must be positive")
        return v


class PaperWheelSchema(BaseModel):
    underlying: str = Field(..., min_length=1, max_length=10)
    strike: float = Field(..., gt=0)
    expiry: str = Field(..., min_length=1)
    premium: float = Field(..., gt=0)
    name: str = Field("")


class GridbotSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    capital: float = Field(..., gt=0)
    grid_count: int = Field(10, gt=0, le=200)
    fee_pct: float = Field(0.1, ge=0, le=10)


class GeoHarmonicSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    n_local: int = Field(233)

    @field_validator("n_local")
    @classmethod
    def _n(cls, v):
        if v not in [144, 233, 377]:
            raise ValueError("must be 144, 233, or 377")
        return v


# GHPineSchema removed with the Pine Script export feature.


class XABCDSchema(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    pct: float = Field(0.03, gt=0, le=1.0)


class AuditLogSchema(BaseModel):
    limit: int = Field(50, gt=0, le=500)
    tool: str = Field("")
    since: str = Field("")


class AuditSummarySchema(BaseModel):
    days: int = Field(7, gt=0, le=90)


# ── Gateway ───────────────────────────────────────────────────────────────────


def _new_id() -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"aud_{ts}_{suffix}"


def _session_suffix(token: str) -> str:
    if not token:
        return "anon"
    return token[-4:] if len(token) >= 4 else token


def _extract_signal(response_text: str, signal_field: Optional[str]) -> Optional[str]:
    if not signal_field:
        return None
    try:
        data = json.loads(response_text)
        if isinstance(data, dict):
            val = data.get(signal_field)
            return str(val) if val is not None else None
    except Exception:
        pass
    return None


def _write_entry(entry: dict) -> None:
    try:
        with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # audit failure must never crash a tool call


def _enrich_response(result: str, entry_id: str, rules_checked: list) -> str:
    audit_stub = {
        "id": entry_id,
        "rules_checked": rules_checked,
        "violations": [],
        "validation_passed": True,
    }
    try:
        data = json.loads(result)
        if isinstance(data, dict):
            data["_audit"] = audit_stub
            return json.dumps(data)
    except Exception:
        pass
    return result + f"\n\n[AUDIT:{json.dumps(audit_stub)}]"


class BansheeGateway:
    def __init__(self, token_fn: Callable[[], str]):
        self._token_fn = token_fn

    def call(
        self,
        tool_name: str,
        params: dict,
        schema_cls: Optional[Type[BaseModel]],
        handler: Callable,
        signal_field: Optional[str] = None,
    ) -> str:
        entry_id = _new_id()
        session = _session_suffix(self._token_fn())
        t0 = time.monotonic()

        entry = {
            "id": entry_id,
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": tool_name,
            "session": session,
            "request": params,
            "validation": {},
            "outcome": {},
        }

        # ── Validate ──────────────────────────────────────────────────────────
        if schema_cls is not None:
            try:
                validated = schema_cls(**params)
                rules_checked = list(schema_cls.model_fields.keys())
                entry["validation"] = {
                    "passed": True,
                    "rules_checked": rules_checked,
                    "violations": [],
                }
            except Exception as exc:
                violations = []
                errors = exc.errors() if hasattr(exc, "errors") else [
                    {"loc": (), "type": "error", "msg": str(exc)}
                ]
                for err in errors:
                    field = ".".join(str(x) for x in err.get("loc", ("unknown",)))
                    violations.append({
                        "field": field,
                        "value": params.get(field),
                        "rule": err.get("type", "validation_error"),
                        "expected": err.get("msg", ""),
                    })
                entry["validation"] = {
                    "passed": False,
                    "rules_checked": [],
                    "violations": violations,
                }
                duration_ms = round((time.monotonic() - t0) * 1000)
                entry["outcome"] = {"status": "rejected", "duration_ms": duration_ms}
                _write_entry(entry)
                return json.dumps({
                    "error": "Validation failed",
                    "violations": violations,
                    "_audit": {"id": entry_id, "validation_passed": False},
                })
        else:
            entry["validation"] = {"passed": True, "rules_checked": [], "violations": []}

        # ── Execute ───────────────────────────────────────────────────────────
        try:
            result = handler(params)
            duration_ms = round((time.monotonic() - t0) * 1000)
            signal = _extract_signal(result, signal_field)
            outcome = {"status": "success", "duration_ms": duration_ms}
            if signal:
                outcome["signal"] = signal
            entry["outcome"] = outcome
            _write_entry(entry)
            return _enrich_response(result, entry_id, entry["validation"]["rules_checked"])
        except Exception as exc:
            duration_ms = round((time.monotonic() - t0) * 1000)
            entry["outcome"] = {"status": "error", "duration_ms": duration_ms, "error": str(exc)}
            _write_entry(entry)
            return json.dumps({
                "error": f"Gateway error: {exc}",
                "tool": tool_name,
                "_audit": {"id": entry_id, "validation_passed": True, "status": "error"},
            })
