from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import mean
from typing import Dict, Iterable, List, Optional


def _as_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


@dataclass
class ExecutionCostModel:
    spread_bps: Decimal = Decimal("2.0")
    slippage_bps: Decimal = Decimal("3.0")
    commission_per_share: Decimal = Decimal("0.0035")
    per_trade_fee: Decimal = Decimal("0.00")

    def __post_init__(self):
        self.spread_bps = _as_decimal(self.spread_bps)
        self.slippage_bps = _as_decimal(self.slippage_bps)
        self.commission_per_share = _as_decimal(self.commission_per_share)
        self.per_trade_fee = _as_decimal(self.per_trade_fee)


@dataclass
class WalkForwardConfig:
    min_train_trades: int = 40
    test_size: int = 20
    step_size: int = 20
    min_test_trades: int = 8
    confidence_candidates: Optional[List[float]] = None

    def __post_init__(self):
        self.min_train_trades = int(self.min_train_trades)
        self.test_size = int(self.test_size)
        self.step_size = int(self.step_size)
        self.min_test_trades = int(self.min_test_trades)
        if self.confidence_candidates is None:
            self.confidence_candidates = [0, 50, 60, 65, 70, 75, 80, 85, 90]


@dataclass
class TradeRecord:
    trade_id: int
    user_id: int
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    ai_confidence: float
    closed_at: datetime


class WalkForwardValidator:
    """Time-ordered walk-forward validator with realistic execution costs."""

    def __init__(self, cost_model: Optional[ExecutionCostModel] = None):
        self.cost_model = cost_model or ExecutionCostModel()

    def _trade_cost(self, trade: TradeRecord) -> Decimal:
        turnover = (trade.entry_price * trade.quantity) + (trade.exit_price * trade.quantity)
        spread_cost = turnover * (self.cost_model.spread_bps / Decimal("10000"))
        slippage_cost = turnover * (self.cost_model.slippage_bps / Decimal("10000"))
        commission_cost = (trade.quantity * self.cost_model.commission_per_share * Decimal("2"))
        return spread_cost + slippage_cost + commission_cost + self.cost_model.per_trade_fee

    def _net_pnl(self, trade: TradeRecord) -> Decimal:
        return trade.gross_pnl - self._trade_cost(trade)

    def _max_drawdown(self, pnl_series: List[Decimal]) -> Decimal:
        equity = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        for pnl in pnl_series:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _ratio(self, numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def _sharpe_sortino(self, pnl_values: List[float]) -> Dict[str, float]:
        if len(pnl_values) < 2:
            return {"sharpe": 0.0, "sortino": 0.0}

        avg = mean(pnl_values)
        variance = mean([(x - avg) ** 2 for x in pnl_values])
        std = sqrt(variance) if variance > 0 else 0.0

        downside = [x for x in pnl_values if x < 0]
        if downside:
            downside_var = mean([x ** 2 for x in downside])
            downside_std = sqrt(downside_var)
        else:
            downside_std = 0.0

        sharpe = self._ratio(avg, std) * sqrt(len(pnl_values)) if std > 0 else 0.0
        sortino = self._ratio(avg, downside_std) * sqrt(len(pnl_values)) if downside_std > 0 else 0.0
        return {"sharpe": sharpe, "sortino": sortino}

    def _metrics(self, trades: List[TradeRecord], strategy_name: str) -> Dict:
        net_values = [self._net_pnl(t) for t in trades]
        gross_values = [t.gross_pnl for t in trades]
        count = len(trades)

        if count == 0:
            return {
                "strategy": strategy_name,
                "trades": 0,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "avg_net_pnl": 0.0,
                "expectancy": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
            }

        wins = [p for p in net_values if p > 0]
        losses = [p for p in net_values if p < 0]

        gross_pnl = sum(gross_values, Decimal("0"))
        net_pnl = sum(net_values, Decimal("0"))
        avg_net = net_pnl / Decimal(count)

        gross_profit = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        win_rate = float(len(wins) / count * 100)

        drawdown = self._max_drawdown(net_values)
        ratio_metrics = self._sharpe_sortino([float(p) for p in net_values])

        return {
            "strategy": strategy_name,
            "trades": count,
            "gross_pnl": float(gross_pnl),
            "net_pnl": float(net_pnl),
            "avg_net_pnl": float(avg_net),
            "expectancy": float(avg_net),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": float(drawdown),
            "sharpe": ratio_metrics["sharpe"],
            "sortino": ratio_metrics["sortino"],
        }

    def _filter_by_confidence(self, trades: List[TradeRecord], threshold: float) -> List[TradeRecord]:
        return [t for t in trades if t.ai_confidence >= threshold]

    def _select_threshold(self, train_trades: List[TradeRecord], candidates: List[float]) -> Dict:
        best = None
        for threshold in candidates:
            subset = self._filter_by_confidence(train_trades, threshold)
            metrics = self._metrics(subset, f"ml_conf>={threshold}")
            score = (metrics["expectancy"], metrics["profit_factor"], metrics["net_pnl"], metrics["trades"])
            if best is None or score > best["score"]:
                best = {
                    "threshold": threshold,
                    "metrics": metrics,
                    "score": score,
                }
        return best or {"threshold": 0.0, "metrics": self._metrics([], "ml_conf>=0"), "score": (0, 0, 0, 0)}

    def _gate_summary(self, metrics: Dict) -> Dict:
        checks = {
            "positive_net_pnl": metrics["net_pnl"] > 0,
            "positive_expectancy": metrics["expectancy"] > 0,
            "profit_factor_gt_1_2": metrics["profit_factor"] > 1.2,
            "max_drawdown_lt_10R": metrics["max_drawdown"] < 10 * abs(metrics["expectancy"]) if metrics["expectancy"] != 0 else False,
            "sharpe_gt_0_5": metrics["sharpe"] > 0.5,
        }
        return {
            "deployment_ready": all(checks.values()),
            "checks": checks,
        }

    def _to_record(self, trade) -> Optional[TradeRecord]:
        closed_at = trade.closed_at or trade.created_at
        if closed_at is None:
            return None
        qty = _as_decimal(trade.quantity)
        entry = _as_decimal(trade.entry_price)
        exit_price = _as_decimal(trade.exit_price)
        gross_pnl = _as_decimal(trade.profit_loss)
        if qty <= 0 or entry <= 0 or exit_price <= 0:
            return None
        return TradeRecord(
            trade_id=trade.id,
            user_id=trade.user_id,
            symbol=(trade.symbol or "").upper(),
            side=(trade.side or "").lower(),
            quantity=qty,
            entry_price=entry,
            exit_price=exit_price,
            gross_pnl=gross_pnl,
            ai_confidence=float(trade.ai_confidence or 0),
            closed_at=closed_at,
        )

    def evaluate(self, trades: Iterable, config: Optional[WalkForwardConfig] = None) -> Dict:
        cfg = config or WalkForwardConfig()
        records = []
        for trade in trades:
            rec = self._to_record(trade)
            if rec is not None:
                records.append(rec)

        records.sort(key=lambda x: x.closed_at)

        if len(records) < cfg.min_train_trades + cfg.min_test_trades:
            return {
                "success": False,
                "error": (
                    f"Need at least {cfg.min_train_trades + cfg.min_test_trades} valid closed trades; "
                    f"got {len(records)}."
                ),
                "records_count": len(records),
            }

        folds = []
        all_baseline_test: List[TradeRecord] = []
        all_ml_test: List[TradeRecord] = []

        train_end = cfg.min_train_trades
        while train_end + cfg.min_test_trades <= len(records):
            test_end = min(train_end + cfg.test_size, len(records))
            train = records[:train_end]
            test = records[train_end:test_end]
            if len(test) < cfg.min_test_trades:
                break

            best = self._select_threshold(train, cfg.confidence_candidates or [0])
            threshold = best["threshold"]

            baseline_train = self._metrics(train, "baseline_all")
            baseline_test = self._metrics(test, "baseline_all")

            ml_train_subset = self._filter_by_confidence(train, threshold)
            ml_test_subset = self._filter_by_confidence(test, threshold)
            ml_train_metrics = self._metrics(ml_train_subset, f"ml_conf>={threshold}")
            ml_test_metrics = self._metrics(ml_test_subset, f"ml_conf>={threshold}")

            all_baseline_test.extend(test)
            all_ml_test.extend(ml_test_subset)

            folds.append({
                "train_start": train[0].closed_at.isoformat(),
                "train_end": train[-1].closed_at.isoformat(),
                "test_start": test[0].closed_at.isoformat(),
                "test_end": test[-1].closed_at.isoformat(),
                "train_trades": len(train),
                "test_trades": len(test),
                "selected_threshold": threshold,
                "baseline_train": baseline_train,
                "baseline_test": baseline_test,
                "ml_train": ml_train_metrics,
                "ml_test": ml_test_metrics,
            })

            train_end += cfg.step_size
            if train_end >= len(records):
                break

        aggregate_baseline = self._metrics(all_baseline_test, "baseline_all_test_combined")
        aggregate_ml = self._metrics(all_ml_test, "ml_gated_test_combined")

        return {
            "success": True,
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "config": {
                "min_train_trades": cfg.min_train_trades,
                "test_size": cfg.test_size,
                "step_size": cfg.step_size,
                "min_test_trades": cfg.min_test_trades,
                "confidence_candidates": cfg.confidence_candidates,
                "cost_model": {
                    "spread_bps": float(self.cost_model.spread_bps),
                    "slippage_bps": float(self.cost_model.slippage_bps),
                    "commission_per_share": float(self.cost_model.commission_per_share),
                    "per_trade_fee": float(self.cost_model.per_trade_fee),
                },
            },
            "input_records": len(records),
            "folds": folds,
            "aggregate": {
                "baseline_all_test": aggregate_baseline,
                "ml_gated_test": aggregate_ml,
                "deployment_gate_baseline": self._gate_summary(aggregate_baseline),
                "deployment_gate_ml": self._gate_summary(aggregate_ml),
            },
        }
