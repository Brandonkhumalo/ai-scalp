import json
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import Trade
from api.trade_data_quality_service import TradeDataQualityAuditor


class Command(BaseCommand):
    help = "Audit trade-data integrity before ML training or walk-forward validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-email",
            type=str,
            default=None,
            help="Optional user email filter.",
        )
        parser.add_argument(
            "--apply-normalization",
            action="store_true",
            help="Normalize side/status/symbol casing in-place.",
        )
        parser.add_argument(
            "--output-json",
            type=str,
            default=None,
            help="Optional path to write full JSON report.",
        )

    def handle(self, *args, **options):
        qs = Trade.objects.all().order_by("created_at")
        user_email = options["user_email"]
        if user_email:
            qs = qs.filter(user__email=user_email)

        auditor = TradeDataQualityAuditor()

        if options["apply_normalization"]:
            changed = auditor.normalize_trade_fields(qs, apply_changes=True)
            self.stdout.write(self.style.SUCCESS(f"Normalized {changed} trades."))

        report = auditor.audit(qs)
        payload = report.__dict__

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Trade Data Quality Audit"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total trades:                 {payload['total_trades']}")
        self.stdout.write(f"Closed trades:                {payload['total_closed_trades']}")
        self.stdout.write(f"Case normalization candidates:{payload['case_normalization_candidates']}")
        self.stdout.write(f"Invalid side values:          {payload['invalid_side_count']}")
        self.stdout.write(f"Invalid status values:        {payload['invalid_status_count']}")
        self.stdout.write(f"Symbol format issues:         {payload['symbol_format_issues']}")
        self.stdout.write(f"P&L mismatches:               {payload['pnl_mismatch_count']}")
        self.stdout.write(f"Missing price fields:         {payload['missing_price_fields_count']}")
        self.stdout.write(f"Temporal issues:              {payload['temporal_issues_count']}")
        self.stdout.write(f"Duplicate groups:             {payload['duplicate_groups_count']}")
        self.stdout.write(f"Duplicate trades:             {payload['duplicate_trade_count']}")

        if payload["pnl_mismatches"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Sample P&L mismatches (first 5):"))
            for row in payload["pnl_mismatches"][:5]:
                self.stdout.write(
                    f"  Trade {row['trade_id']} {row['symbol']} {row['side']} "
                    f"expected={row['expected_pnl']:.4f} observed={row['observed_pnl']:.4f} diff={row['diff']:.4f}"
                )

        output_json = options["output_json"]
        if output_json:
            target = Path(output_json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"Wrote JSON report: {target}"))
