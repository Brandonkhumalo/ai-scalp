import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import Trade
from api.trade_data_quality_service import TradeDataQualityAuditor
from api.walkforward_service import ExecutionCostModel, WalkForwardConfig, WalkForwardValidator


class Command(BaseCommand):
    help = "Run out-of-sample walk-forward validation with execution costs."

    def add_arguments(self, parser):
        parser.add_argument("--user-email", type=str, default=None, help="Optional user email filter.")
        parser.add_argument("--min-train-trades", type=int, default=40)
        parser.add_argument("--test-size", type=int, default=20)
        parser.add_argument("--step-size", type=int, default=20)
        parser.add_argument("--min-test-trades", type=int, default=8)
        parser.add_argument("--spread-bps", type=float, default=2.0)
        parser.add_argument("--slippage-bps", type=float, default=3.0)
        parser.add_argument("--commission-per-share", type=float, default=0.0035)
        parser.add_argument("--per-trade-fee", type=float, default=0.00)
        parser.add_argument(
            "--output-json",
            type=str,
            default=None,
            help="Optional output path. Default: backend/reports/walkforward_<timestamp>.json",
        )

    def handle(self, *args, **options):
        qs = Trade.objects.filter(status="closed").order_by("closed_at", "created_at")
        if options["user_email"]:
            qs = qs.filter(user__email=options["user_email"])

        # Always run data audit before evaluation so reports include quality context.
        auditor = TradeDataQualityAuditor()
        audit_report = auditor.audit(qs)

        cost_model = ExecutionCostModel(
            spread_bps=options["spread_bps"],
            slippage_bps=options["slippage_bps"],
            commission_per_share=options["commission_per_share"],
            per_trade_fee=options["per_trade_fee"],
        )
        cfg = WalkForwardConfig(
            min_train_trades=options["min_train_trades"],
            test_size=options["test_size"],
            step_size=options["step_size"],
            min_test_trades=options["min_test_trades"],
        )

        validator = WalkForwardValidator(cost_model=cost_model)
        result = validator.evaluate(qs, config=cfg)
        result["data_quality"] = audit_report.__dict__

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Walk-Forward Validation"))
        self.stdout.write("=" * 70)

        if not result.get("success"):
            self.stdout.write(self.style.ERROR(result.get("error", "Validation failed.")))
        else:
            baseline = result["aggregate"]["baseline_all_test"]
            ml = result["aggregate"]["ml_gated_test"]
            baseline_gate = result["aggregate"]["deployment_gate_baseline"]["deployment_ready"]
            ml_gate = result["aggregate"]["deployment_gate_ml"]["deployment_ready"]

            self.stdout.write(f"Input records: {result['input_records']}")
            self.stdout.write(f"Folds:         {len(result['folds'])}")
            self.stdout.write("")
            self.stdout.write("Baseline (all test trades):")
            self.stdout.write(
                f"  trades={baseline['trades']} net_pnl={baseline['net_pnl']:.2f} "
                f"expectancy={baseline['expectancy']:.4f} win_rate={baseline['win_rate']:.2f}% "
                f"pf={baseline['profit_factor']:.2f} mdd={baseline['max_drawdown']:.2f}"
            )
            self.stdout.write(f"  deployment_ready={baseline_gate}")
            self.stdout.write("")
            self.stdout.write("ML-gated (test trades after thresholding):")
            self.stdout.write(
                f"  trades={ml['trades']} net_pnl={ml['net_pnl']:.2f} "
                f"expectancy={ml['expectancy']:.4f} win_rate={ml['win_rate']:.2f}% "
                f"pf={ml['profit_factor']:.2f} mdd={ml['max_drawdown']:.2f}"
            )
            self.stdout.write(f"  deployment_ready={ml_gate}")

        output_path = options["output_json"]
        if not output_path:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = f"backend/reports/walkforward_{ts}.json"

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2), encoding="utf-8")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Saved report: {target}"))
