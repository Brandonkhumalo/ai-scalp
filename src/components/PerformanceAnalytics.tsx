import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Award,
  Activity,
  DollarSign,
  Percent,
  BarChart3
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatPercentage, formatNumber } from "@/lib/formatters";

interface PerformanceMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalProfit: number;
  totalLoss: number;
  netPnL: number;
  averageWin: number;
  averageLoss: number;
  profitFactor: number;
  largestWin: number;
  largestLoss: number;
  averageHoldTime: string;
  roi: number;
}

export const PerformanceAnalytics = () => {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    totalTrades: 0,
    winningTrades: 0,
    losingTrades: 0,
    winRate: 0,
    totalProfit: 0,
    totalLoss: 0,
    netPnL: 0,
    averageWin: 0,
    averageLoss: 0,
    profitFactor: 0,
    largestWin: 0,
    largestLoss: 0,
    averageHoldTime: "0h",
    roi: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        // Fetch real performance metrics from Alpaca API
        const response = await fetch('/api/performance-analytics/', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch performance analytics');
        }
        
        const data = await response.json();
        
        setMetrics({
          totalTrades: data.totalTrades || 0,
          winningTrades: data.winningTrades || 0,
          losingTrades: data.losingTrades || 0,
          winRate: data.winRate || 0,
          totalProfit: data.totalProfit || 0,
          totalLoss: data.totalLoss || 0,
          netPnL: data.netPnL || 0,
          averageWin: data.averageWin || 0,
          averageLoss: data.averageLoss || 0,
          profitFactor: data.profitFactor || 0,
          largestWin: data.largestWin || 0,
          largestLoss: data.largestLoss || 0,
          averageHoldTime: data.averageHoldTime || '0h',
          roi: data.roi || 0
        });
      } catch (error) {
        console.error('Error loading performance metrics:', error);
      } finally {
        setLoading(false);
      }
    };

    loadMetrics();
    
    // Refresh metrics every 30 seconds (real Alpaca data)
    const interval = setInterval(loadMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-8 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  const winRateColor = metrics.winRate >= 60 ? "text-accent" : metrics.winRate >= 40 ? "text-yellow-500" : "text-destructive";
  const profitFactorColor = metrics.profitFactor >= 2 ? "text-accent" : metrics.profitFactor >= 1 ? "text-yellow-500" : "text-destructive";
  const roiColor = metrics.roi > 0 ? "text-accent" : "text-destructive";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Performance Analytics
          </CardTitle>
        </CardHeader>
        <CardContent>
          {metrics.totalTrades === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No closed trades yet. Start trading to see your performance metrics.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Win Rate */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Win Rate</span>
                  </div>
                  <Badge variant={metrics.winRate >= 50 ? "default" : "destructive"}>
                    {metrics.winningTrades}W/{metrics.losingTrades}L
                  </Badge>
                </div>
                <div className={`text-2xl font-bold ${winRateColor}`}>
                  {formatPercentage(metrics.winRate, 1)}
                </div>
                <Progress value={metrics.winRate} className="mt-2 h-2" />
              </div>

              {/* Profit Factor */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Award className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Profit Factor</span>
                  </div>
                </div>
                <div className={`text-2xl font-bold ${profitFactorColor}`}>
                  {metrics.profitFactor >= 999 ? "∞" : metrics.profitFactor.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  {metrics.profitFactor >= 2 ? "Excellent" : metrics.profitFactor >= 1 ? "Good" : "Poor"}
                </div>
              </div>

              {/* Net P&L */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Net P&L</span>
                  </div>
                  {metrics.netPnL >= 0 ? (
                    <TrendingUp className="h-4 w-4 text-accent" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-destructive" />
                  )}
                </div>
                <div className={`text-2xl font-bold ${metrics.netPnL >= 0 ? 'text-accent' : 'text-destructive'}`}>
                  {formatCurrency(metrics.netPnL)}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  {metrics.totalTrades} total trades
                </div>
              </div>

              {/* ROI */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Percent className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">ROI</span>
                  </div>
                </div>
                <div className={`text-2xl font-bold ${roiColor}`}>
                  {metrics.roi >= 0 ? '+' : ''}{formatPercentage(metrics.roi, 2)}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  Return on investment
                </div>
              </div>

              {/* Average Win */}
              <div className="p-4 bg-accent/10 rounded-lg border border-accent/20">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-4 w-4 text-accent" />
                  <span className="text-sm text-muted-foreground">Avg Win</span>
                </div>
                <div className="text-xl font-bold text-accent">
                  {formatCurrency(metrics.averageWin)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Largest: {formatCurrency(metrics.largestWin)}
                </div>
              </div>

              {/* Average Loss */}
              <div className="p-4 bg-destructive/10 rounded-lg border border-destructive/20">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingDown className="h-4 w-4 text-destructive" />
                  <span className="text-sm text-muted-foreground">Avg Loss</span>
                </div>
                <div className="text-xl font-bold text-destructive">
                  {formatCurrency(metrics.averageLoss)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Largest: {formatCurrency(metrics.largestLoss)}
                </div>
              </div>

              {/* Total Profit */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Total Profit</span>
                </div>
                <div className="text-xl font-bold text-accent">
                  {formatCurrency(metrics.totalProfit)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  From {metrics.winningTrades} winning trades
                </div>
              </div>

              {/* Average Hold Time */}
              <div className="p-4 bg-secondary rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Avg Hold Time</span>
                </div>
                <div className="text-xl font-bold">
                  {metrics.averageHoldTime}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Per trade duration
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
