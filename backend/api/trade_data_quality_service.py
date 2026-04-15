from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Tuple


def _as_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def normalize_side(side: Optional[str]) -> str:
    return (side or "").strip().lower()


def normalize_status(status: Optional[str]) -> str:
    return (status or "").strip().lower()


def normalize_symbol(symbol: Optional[str]) -> str:
    return (symbol or "").strip().upper()


def _trade_fingerprint(trade) -> Tuple:
    closed_at = trade.closed_at.isoformat(timespec="seconds") if trade.closed_at else "none"
    return (
        trade.user_id,
        normalize_symbol(trade.symbol),
        normalize_side(trade.side),
        f"{_as_decimal(trade.quantity):.8f}",
        f"{_as_decimal(trade.entry_price):.2f}",
        f"{_as_decimal(trade.exit_price):.2f}",
        closed_at,
    )


@dataclass
class AuditResult:
    total_trades: int
    total_closed_trades: int
    case_normalization_candidates: int
    invalid_side_count: int
    invalid_status_count: int
    symbol_format_issues: int
    pnl_mismatch_count: int
    missing_price_fields_count: int
    temporal_issues_count: int
    duplicate_groups_count: int
    duplicate_trade_count: int
    duplicate_groups: List[List[int]]
    pnl_mismatches: List[Dict]


class TradeDataQualityAuditor:
    """Audits closed-trade integrity before training or walk-forward validation."""

    def __init__(self, pnl_tolerance: Decimal = Decimal("0.05")):
        self.pnl_tolerance = pnl_tolerance

    def _expected_pnl(self, trade) -> Optional[Decimal]:
        qty = _as_decimal(trade.quantity)
        entry = _as_decimal(trade.entry_price)
        exit_price = _as_decimal(trade.exit_price)
        side = normalize_side(trade.side)

        if qty <= 0 or entry <= 0 or exit_price <= 0:
            return None

        if side == "buy":
            return (exit_price - entry) * qty
        if side == "sell":
            return (entry - exit_price) * qty
        return None

    def audit(self, trades: Iterable) -> AuditResult:
        trades = list(trades)
        closed = [t for t in trades if normalize_status(getattr(t, "status", "")) == "closed"]

        valid_sides = {"buy", "sell"}
        valid_statuses = {"pending", "open", "closed", "cancelled", "failed"}

        case_normalization_candidates = 0
        invalid_side_count = 0
        invalid_status_count = 0
        symbol_format_issues = 0
        pnl_mismatch_count = 0
        missing_price_fields_count = 0
        temporal_issues_count = 0

        pnl_mismatches: List[Dict] = []
        duplicates = defaultdict(list)

        for trade in trades:
            side_norm = normalize_side(trade.side)
            status_norm = normalize_status(trade.status)
            symbol_norm = normalize_symbol(trade.symbol)

            if trade.side != side_norm or trade.status != status_norm or trade.symbol != symbol_norm:
                case_normalization_candidates += 1

            if side_norm not in valid_sides:
                invalid_side_count += 1

            if status_norm not in valid_statuses:
                invalid_status_count += 1

            if trade.symbol != symbol_norm:
                symbol_format_issues += 1

            if trade.created_at and trade.closed_at and trade.closed_at < trade.created_at:
                temporal_issues_count += 1

            if status_norm == "closed":
                if not trade.exit_price or not trade.entry_price or not trade.quantity:
                    missing_price_fields_count += 1
                else:
                    expected = self._expected_pnl(trade)
                    observed = _as_decimal(trade.profit_loss)
                    if expected is None:
                        missing_price_fields_count += 1
                    else:
                        diff = abs(expected - observed)
                        if diff > self.pnl_tolerance:
                            pnl_mismatch_count += 1
                            pnl_mismatches.append({
                                "trade_id": trade.id,
                                "symbol": symbol_norm,
                                "side": side_norm,
                                "expected_pnl": float(expected),
                                "observed_pnl": float(observed),
                                "diff": float(diff),
                            })

            duplicates[_trade_fingerprint(trade)].append(trade.id)

        duplicate_groups = [ids for ids in duplicates.values() if len(ids) > 1]
        duplicate_trade_count = sum(len(ids) for ids in duplicate_groups)

        return AuditResult(
            total_trades=len(trades),
            total_closed_trades=len(closed),
            case_normalization_candidates=case_normalization_candidates,
            invalid_side_count=invalid_side_count,
            invalid_status_count=invalid_status_count,
            symbol_format_issues=symbol_format_issues,
            pnl_mismatch_count=pnl_mismatch_count,
            missing_price_fields_count=missing_price_fields_count,
            temporal_issues_count=temporal_issues_count,
            duplicate_groups_count=len(duplicate_groups),
            duplicate_trade_count=duplicate_trade_count,
            duplicate_groups=duplicate_groups[:50],
            pnl_mismatches=pnl_mismatches[:100],
        )

    def normalize_trade_fields(self, trades: Iterable, apply_changes: bool = False) -> int:
        """
        Normalizes side/status/symbol casing.
        Returns number of rows that require/received updates.
        """
        changed = 0
        for trade in trades:
            new_side = normalize_side(trade.side)
            new_status = normalize_status(trade.status)
            new_symbol = normalize_symbol(trade.symbol)

            if trade.side != new_side or trade.status != new_status or trade.symbol != new_symbol:
                changed += 1
                if apply_changes:
                    trade.side = new_side
                    trade.status = new_status
                    trade.symbol = new_symbol
                    trade.save(update_fields=["side", "status", "symbol"])
        return changed
