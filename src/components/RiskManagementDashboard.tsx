import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Shield, 
  AlertTriangle, 
  TrendingUp,
  DollarSign,
  Percent,
  Activity,
  Target
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatPercentage } from "@/lib/formatters";

interface RiskMetrics {
  accountBalance: number;
  totalExposure: number;
  exposurePercent: number;
  dailyLoss: number;
  dailyLossPercent: number;
  maxDailyLossLimit: number;
  openPositions: number;
  maxPositions: number;
  largestPosition: number;
  largestPositionPercent: number;
  portfolioDiversity: number;
  riskLevel: "low" | "medium" | "high" | "critical";
}

export const RiskManagementDashboard = () => {
  const [metrics, setMetrics] = useState<RiskMetrics>({
    accountBalance: 0,
    totalExposure: 0,
    exposurePercent: 0,
    dailyLoss: 0,
    dailyLossPercent: 0,
    maxDailyLossLimit: 5, // 5% max daily loss
    openPositions: 0,
    maxPositions: 10,
    largestPosition: 0,
    largestPositionPercent: 0,
    portfolioDiversity: 0,
    riskLevel: "low"
  });
  const [alerts, setAlerts] = useState<string[]>([]);

  useEffect(() => {
    const loadRiskMetrics = async () => {
      try {
        const [profile, trades] = await Promise.all([
          apiClient.getProfile(),
          apiClient.getTrades()
        ]);

        const accountBalance = parseFloat(profile.usd_balance || 0);
        const openTrades = trades.filter((t: any) => t.status === 'open');
        
        // Calculate total exposure
        const totalExposure = openTrades.reduce((sum: number, t: any) => {
          return sum + (t.entry_price * t.quantity);
        }, 0);

        const exposurePercent = accountBalance > 0 ? (totalExposure / accountBalance) * 100 : 0;

        // Calculate daily loss
        const today = new Date().toISOString().split('T')[0];
        const todayTrades = trades.filter((t: any) => 
          t.status === 'closed' && t.closed_at?.startsWith(today)
        );
        const dailyLoss = todayTrades.reduce((sum: number, t: any) => {
          const pnl = t.profit_loss || 0;
          return pnl < 0 ? sum + Math.abs(pnl) : sum;
        }, 0);
        const dailyLossPercent = accountBalance > 0 ? (dailyLoss / accountBalance) * 100 : 0;

        // Find largest position
        const largestPosition = openTrades.length > 0
          ? Math.max(...openTrades.map((t: any) => t.entry_price * t.quantity))
          : 0;
        const largestPositionPercent = accountBalance > 0 ? (largestPosition / accountBalance) * 100 : 0;

        // Calculate portfolio diversity (number of unique symbols)
        const uniqueSymbols = new Set(openTrades.map((t: any) => t.symbol));
        const portfolioDiversity = uniqueSymbols.size;

        // Determine risk level
        let riskLevel: "low" | "medium" | "high" | "critical" = "low";
        const newAlerts: string[] = [];

        if (dailyLossPercent >= metrics.maxDailyLossLimit) {
          riskLevel = "critical";
          newAlerts.push(`Daily loss limit reached (${formatPercentage(dailyLossPercent, 1)})`);
        } else if (dailyLossPercent >= metrics.maxDailyLossLimit * 0.8) {
          riskLevel = "high";
          newAlerts.push(`Approaching daily loss limit (${formatPercentage(dailyLossPercent, 1)})`);
        } else if (exposurePercent > 80) {
          riskLevel = "high";
          newAlerts.push(`High account exposure (${formatPercentage(exposurePercent, 1)})`);
        } else if (exposurePercent > 50) {
          riskLevel = "medium";
        }

        if (largestPositionPercent > 20) {
          newAlerts.push(`Large single position: ${formatPercentage(largestPositionPercent, 1)} of account`);
        }

        if (openTrades.length >= metrics.maxPositions) {
          newAlerts.push(`Maximum positions reached (${openTrades.length}/${metrics.maxPositions})`);
        }

        if (portfolioDiversity <= 2 && openTrades.length > 0) {
          newAlerts.push(`Low portfolio diversity (${portfolioDiversity} symbols)`);
        }

        setMetrics({
          accountBalance,
          totalExposure,
          exposurePercent,
          dailyLoss,
          dailyLossPercent,
          maxDailyLossLimit: 5,
          openPositions: openTrades.length,
          maxPositions: 10,
          largestPosition,
          largestPositionPercent,
          portfolioDiversity,
          riskLevel
        });

        setAlerts(newAlerts);
      } catch (error) {
        console.error('Error loading risk metrics:', error);
      }
    };

    loadRiskMetrics();
    
    // Update every 5 seconds
    const interval = setInterval(loadRiskMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  const getRiskColor = () => {
    switch (metrics.riskLevel) {
      case "critical": return "text-red-500";
      case "high": return "text-orange-500";
      case "medium": return "text-yellow-500";
      default: return "text-accent";
    }
  };

  const getRiskBadge = () => {
    switch (metrics.riskLevel) {
      case "critical": return <Badge variant="destructive">CRITICAL</Badge>;
      case "high": return <Badge className="bg-orange-500">HIGH</Badge>;
      case "medium": return <Badge className="bg-yellow-500">MEDIUM</Badge>;
      default: return <Badge variant="default">LOW</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Management
          </CardTitle>
          {getRiskBadge()}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Risk Alerts */}
        {alerts.length > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="space-y-1">
                {alerts.map((alert, i) => (
                  <div key={i} className="text-sm">{alert}</div>
                ))}
              </div>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Daily Loss Limit */}
          <div className="p-4 bg-secondary rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Daily Loss</span>
              </div>
              <span className={`text-sm font-semibold ${metrics.dailyLossPercent > 0 ? 'text-destructive' : 'text-muted-foreground'}`}>
                {formatPercentage(metrics.dailyLossPercent, 1)} / {formatPercentage(metrics.maxDailyLossLimit, 0)}
              </span>
            </div>
            <Progress 
              value={metrics.dailyLossPercent} 
              className="h-2 mb-2"
              max={metrics.maxDailyLossLimit}
            />
            <div className="text-xs text-muted-foreground">
              Loss today: {formatCurrency(metrics.dailyLoss)}
            </div>
          </div>

          {/* Account Exposure */}
          <div className="p-4 bg-secondary rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Exposure</span>
              </div>
              <span className="text-sm font-semibold">
                {formatPercentage(metrics.exposurePercent, 1)}
              </span>
            </div>
            <Progress value={metrics.exposurePercent} className="h-2 mb-2" />
            <div className="text-xs text-muted-foreground">
              {formatCurrency(metrics.totalExposure)} / {formatCurrency(metrics.accountBalance)}
            </div>
          </div>

          {/* Open Positions */}
          <div className="p-4 bg-secondary rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Open Positions</span>
              </div>
              <span className="text-sm font-semibold">
                {metrics.openPositions} / {metrics.maxPositions}
              </span>
            </div>
            <Progress 
              value={(metrics.openPositions / metrics.maxPositions) * 100} 
              className="h-2 mb-2"
            />
            <div className="text-xs text-muted-foreground">
              Portfolio diversity: {metrics.portfolioDiversity} symbols
            </div>
          </div>

          {/* Largest Position */}
          <div className="p-4 bg-secondary rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Largest Position</span>
              </div>
              <span className="text-sm font-semibold">
                {formatPercentage(metrics.largestPositionPercent, 1)}
              </span>
            </div>
            <Progress value={metrics.largestPositionPercent} className="h-2 mb-2" />
            <div className="text-xs text-muted-foreground">
              {formatCurrency(metrics.largestPosition)} exposure
            </div>
          </div>
        </div>

        {/* Risk Summary */}
        <div className={`p-4 rounded-lg border-2 ${
          metrics.riskLevel === "critical" ? "bg-red-500/10 border-red-500/30" :
          metrics.riskLevel === "high" ? "bg-orange-500/10 border-orange-500/30" :
          metrics.riskLevel === "medium" ? "bg-yellow-500/10 border-yellow-500/30" :
          "bg-accent/10 border-accent/30"
        }`}>
          <div className="flex items-center justify-between">
            <div>
              <div className={`text-lg font-bold ${getRiskColor()}`}>
                Risk Level: {metrics.riskLevel.toUpperCase()}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {metrics.riskLevel === "critical" ? "Trading halted - reduce exposure immediately" :
                 metrics.riskLevel === "high" ? "High risk - consider reducing positions" :
                 metrics.riskLevel === "medium" ? "Moderate risk - monitor closely" :
                 "Risk within acceptable limits"}
              </div>
            </div>
            <Shield className={`h-8 w-8 ${getRiskColor()}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
