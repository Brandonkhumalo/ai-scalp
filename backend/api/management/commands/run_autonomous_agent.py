import logging
import sys
from django.core.management.base import BaseCommand
from api.autonomous_agent_service import AutonomousAgentService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the Autonomous Trading Agent - 24/7 Multi-Timezone Market Orchestrator'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        
        logger.info("╔════════════════════════════════════════════════════════════════╗")
        logger.info("║     🤖 AUTONOMOUS TRADING AGENT - STOCKS ONLY                ║")
        logger.info("╠════════════════════════════════════════════════════════════════╣")
        logger.info("║  Markets Monitored (Stocks):                                   ║")
        logger.info("║    • US Markets (NYSE/NASDAQ)  - 09:30-16:00 EST             ║")
        logger.info("║    • EU Markets (LSE/Euronext) - 08:00-16:30 GMT             ║")
        logger.info("║    • Forex: MANUAL TRADING ONLY (Not in autonomous agent)     ║")
        logger.info("║                                                                ║")
        logger.info("║  Features:                                                     ║")
        logger.info("║    ✓ Automatic market hours detection                         ║")
        logger.info("║    ✓ Multi-account orchestration (Alpaca + Capital stocks)    ║")
        logger.info("║    ✓ Overlapping market handling (US/EU)                      ║")
        logger.info("║    ✓ Real-time analytics monitoring                           ║")
        logger.info("║    ✓ Risk management & daily loss limits                      ║")
        logger.info("╚════════════════════════════════════════════════════════════════╝")
        logger.info("")
        
        try:
            agent = AutonomousAgentService()
            agent.run_continuous(check_interval=interval)
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Autonomous Agent shutdown initiated...")
            logger.info("✅ Agent stopped gracefully")
            sys.exit(0)
        except Exception as e:
            logger.error(f"❌ Fatal error in Autonomous Agent: {e}", exc_info=True)
            sys.exit(1)
