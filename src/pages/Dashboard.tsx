import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Activity, 
  TrendingUp,
  TrendingDown, 
  DollarSign, 
  Brain,
  Power,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  Settings,
  LogOut,
  Shield,
  FileText,
  Users,
  Menu,
  X,
  Bot
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { useUserRole } from "@/hooks/useUserRole";
import { UnifiedTradeForm } from "@/components/UnifiedTradeForm";
import { LiveMarketData } from "@/components/LiveMarketData";
import { LivePriceTicker } from "@/components/LivePriceTicker";
import { AdvancedOrderTypes } from "@/components/AdvancedOrderTypes";
import { PerformanceAnalytics } from "@/components/PerformanceAnalytics";
import { MarketWatchlist } from "@/components/MarketWatchlist";
import { RiskManagementDashboard } from "@/components/RiskManagementDashboard";
import { PnLChart } from "@/components/PnLChart";
import { AutonomousAgentControl } from "@/components/AutonomousAgentControl";
import { useTrading } from "@/contexts/TradingContext";
import { formatCurrency, formatProfitLoss, formatNumber } from "@/lib/formatters";

const Dashboard = () => {
  const [profile, setProfile] = useState<any>(null);
  const [alpacaAccount, setAlpacaAccount] = useState<any>(null);
  const [alpacaError, setAlpacaError] = useState<boolean>(false);
  const [capitalUseDemo, setCapitalUseDemo] = useState<boolean>(true);
  const [capitalModeUpdating, setCapitalModeUpdating] = useState<boolean>(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userRoles, setUserRoles] = useState<string[]>([]);
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const {
    aiEnabled,
    setAiEnabled,
    positions: globalPositions,
    recentTrades: globalRecentTrades,
    signals,
    dailyPnL,
    totalPnL,
    tradeCount,
    refreshTrades
  } = useTrading();

  useEffect(() => {
    const loadData = async () => {
      if (!apiClient.isAuthenticated()) {
        navigate("/auth");
        return;
      }

      try {
        // Get roles from /me endpoint
        const meData = await apiClient.getMe();
        setUserRoles(meData.roles || []);
        
        // Get profile data
        const profileData = await apiClient.getProfile();
        setProfile(profileData);
        setCapitalUseDemo(profileData?.capital_use_demo ?? true);
        
        // Get Alpaca account data
        try {
          const alpacaData = await apiClient.get('/alpaca-account/');
          setAlpacaAccount(alpacaData);
          setAlpacaError(false);
        } catch (error) {
          console.error('Error fetching Alpaca account:', error);
          setAlpacaError(true);
        }
      } catch (error) {
        navigate("/auth");
      }
    };

    loadData();
    
    // Set up real-time balance updates every 15 seconds (reduced to avoid API rate limits)
    const balanceInterval = setInterval(async () => {
      if (apiClient.isAuthenticated()) {
        try {
          const profileData = await apiClient.getProfile();
          setProfile(profileData);
          setCapitalUseDemo(profileData?.capital_use_demo ?? true);
          
          // Also refresh Alpaca balance
          try {
            const alpacaData = await apiClient.get('/alpaca-account/');
            setAlpacaAccount(alpacaData);
            setAlpacaError(false);
          } catch (error) {
            console.error('Error updating Alpaca balance:', error);
            setAlpacaError(true);
          }
        } catch (error) {
          console.error('Error updating balance:', error);
        }
      }
    }, 15000);
    
    return () => clearInterval(balanceInterval);
  }, [navigate]);

  const handleLogout = async () => {
    await apiClient.logout();
    navigate("/");
  };

  const toggleCapitalMode = async () => {
    const nextMode = !capitalUseDemo;
    setCapitalModeUpdating(true);
    try {
      await apiClient.toggleCapitalDemoMode(nextMode);
      setCapitalUseDemo(nextMode);
      toast({
        title: "Trading Mode Updated",
        description: `Capital.com mode set to ${nextMode ? "Demo" : "Live"}`,
      });
    } catch (error: any) {
      toast({
        title: "Mode Switch Failed",
        description: error?.message || "Could not switch Capital.com mode",
        variant: "destructive",
      });
    } finally {
      setCapitalModeUpdating(false);
    }
  };

  const handleCloseTrade = async (trade: any) => {
    try {
      const profitLoss = trade.profit_loss !== undefined ? trade.profit_loss : trade.pnl;
      
      if (profitLoss === undefined || profitLoss === null) {
        toast({
          title: "Error",
          description: "Cannot calculate profit/loss for this trade",
          variant: "destructive",
        });
        return;
      }
      
      let currentPrice;
      
      if (trade.side === "BUY" || trade.side === "buy") {
        currentPrice = parseFloat(trade.entry_price) + (profitLoss / trade.quantity);
      } else {
        currentPrice = parseFloat(trade.entry_price) - (profitLoss / trade.quantity);
      }
      
      await apiClient.closeTrade(trade.id, currentPrice, profitLoss);
      
      const updatedProfile = await apiClient.getProfile();
      setProfile(updatedProfile);
      
      refreshTrades();
      
      toast({
        title: "Trade Closed",
        description: `Successfully closed ${trade.symbol} with ${profitLoss >= 0 ? 'profit' : 'loss'} of $${Math.abs(profitLoss).toFixed(2)}`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to close trade",
        variant: "destructive",
      });
    }
  };

  const displayPositions = [...globalPositions].sort((a, b) => {
    const pnlA = a.profit_loss !== undefined ? a.profit_loss : a.pnl;
    const pnlB = b.profit_loss !== undefined ? b.profit_loss : b.pnl;
    const profitPercentA = pnlA && a.entry_price 
      ? (pnlA / ((typeof a.entry_price === 'number' ? a.entry_price : parseFloat(a.entry_price)) * a.quantity)) * 100 
      : 0;
    const profitPercentB = pnlB && b.entry_price 
      ? (pnlB / ((typeof b.entry_price === 'number' ? b.entry_price : parseFloat(b.entry_price)) * b.quantity)) * 100 
      : 0;
    
    const canTakeProfitA = profitPercentA > 20;
    const canTakeProfitB = profitPercentB > 20;
    
    if (canTakeProfitA && !canTakeProfitB) return -1;
    if (!canTakeProfitA && canTakeProfitB) return 1;
    
    return profitPercentB - profitPercentA;
  });
  const displayRecentTrades = globalRecentTrades;
  const displaySignals = signals;

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Activity className="h-6 w-6 text-primary" />
              <h1 className="text-lg sm:text-xl font-bold gradient-primary bg-clip-text text-transparent">ZimAI Trader</h1>
            </div>
            
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-4 flex-1 overflow-hidden">
              <div className="flex gap-3 text-sm overflow-x-auto scrollbar-hide whitespace-nowrap flex-1">
                <Link to="/dashboard" className="text-foreground font-semibold">Stocks</Link>
                <Link to="/trade" className="text-muted-foreground hover:text-foreground transition-smooth">Trade</Link>
                <Link to="/history" className="text-muted-foreground hover:text-foreground transition-smooth">History</Link>
                <Link to="/balance-history" className="text-muted-foreground hover:text-foreground transition-smooth">Balance</Link>
                {userRoles && userRoles.includes('admin') && (
                  <Link to="/admin" className="text-muted-foreground hover:text-foreground transition-smooth">Admin</Link>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link to="/profile">
                  <Button variant="ghost" size="icon">
                    <Settings className="h-5 w-5" />
                  </Button>
                </Link>
                <Button variant="ghost" size="icon" onClick={handleLogout}>
                  <LogOut className="h-5 w-5" />
                </Button>
              </div>
            </div>

            {/* Mobile Menu Button */}
            <Button 
              variant="ghost" 
              size="icon" 
              className="md:hidden"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>

          {/* Mobile Navigation Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden mt-4 pb-4 border-t border-border pt-4">
              <div className="flex flex-col gap-3">
                <Link to="/dashboard" className="text-foreground font-semibold py-2" onClick={() => setMobileMenuOpen(false)}>Stocks</Link>
                <Link to="/trade" className="text-muted-foreground hover:text-foreground transition-smooth py-2" onClick={() => setMobileMenuOpen(false)}>Trade</Link>
                <Link to="/history" className="text-muted-foreground hover:text-foreground transition-smooth py-2" onClick={() => setMobileMenuOpen(false)}>History</Link>
                <Link to="/balance-history" className="text-muted-foreground hover:text-foreground transition-smooth py-2" onClick={() => setMobileMenuOpen(false)}>Balance History</Link>
                {userRoles && userRoles.includes('admin') && (
                  <Link to="/admin" className="text-muted-foreground hover:text-foreground transition-smooth py-2" onClick={() => setMobileMenuOpen(false)}>Admin</Link>
                )}
                <div className="flex items-center gap-2 pt-2 border-t border-border mt-2">
                  <Link to="/profile" className="flex-1" onClick={() => setMobileMenuOpen(false)}>
                    <Button variant="ghost" size="sm" className="w-full">
                      <Settings className="h-4 w-4 mr-2" />
                      Profile
                    </Button>
                  </Link>
                  <Button variant="ghost" size="sm" className="flex-1" onClick={handleLogout}>
                    <LogOut className="h-4 w-4 mr-2" />
                    Logout
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <LivePriceTicker />
        
        <Tabs defaultValue="overview" className="space-y-6 mt-6">
          <TabsList className="inline-flex w-full sm:w-auto overflow-x-auto">
            <TabsTrigger value="overview" className="whitespace-nowrap">
              Overview
            </TabsTrigger>
            <TabsTrigger value="ai-agent" className="whitespace-nowrap">
              <Bot className="h-4 w-4 mr-2" />
              AI Agent
            </TabsTrigger>
            <TabsTrigger value="pro-tools" className="whitespace-nowrap">
              Pro Tools
            </TabsTrigger>
            <TabsTrigger value="live-data" className="whitespace-nowrap">
              Live Market Data
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
        {/* Enterprise Controls - Only visible to admin/compliance/auditor roles */}
        {userRoles && userRoles.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Enterprise Controls
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {userRoles.includes('admin') && (
                <Card className="p-4 bg-card border-border hover:bg-accent/5 cursor-pointer transition-smooth" onClick={() => navigate('/admin')}>
                  <Users className="h-8 w-8 text-primary mb-2" />
                  <h3 className="font-semibold mb-1">Admin Panel</h3>
                  <p className="text-xs text-muted-foreground">Manage user roles</p>
                </Card>
              )}
              {(userRoles.includes('admin') || userRoles.includes('auditor')) && (
                <Card className="p-4 bg-card border-border hover:bg-accent/5 cursor-pointer transition-smooth" onClick={() => navigate('/audit-log')}>
                  <FileText className="h-8 w-8 text-primary mb-2" />
                  <h3 className="font-semibold mb-1">Audit Log</h3>
                  <p className="text-xs text-muted-foreground">View system history</p>
                </Card>
              )}
              {(userRoles.includes('admin') || userRoles.includes('trader') || userRoles.includes('operator')) && (
                <Card className="p-4 bg-card border-border hover:bg-accent/5 cursor-pointer transition-smooth" onClick={() => navigate('/model-registry')}>
                  <Brain className="h-8 w-8 text-primary mb-2" />
                  <h3 className="font-semibold mb-1">Model Registry</h3>
                  <p className="text-xs text-muted-foreground">AI governance</p>
                </Card>
              )}
              {(userRoles.includes('admin') || userRoles.includes('compliance')) && (
                <Card className="p-4 bg-card border-border hover:bg-accent/5 cursor-pointer transition-smooth" onClick={() => navigate('/compliance')}>
                  <Shield className="h-8 w-8 text-primary mb-2" />
                  <h3 className="font-semibold mb-1">Compliance</h3>
                  <p className="text-xs text-muted-foreground">KYC/AML monitoring</p>
                </Card>
              )}
            </div>
          </div>
        )}

        {/* Account Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 mb-8">
          <Card className="p-6 bg-card border-border border-l-4 border-l-blue-500">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Capital Balance</span>
              <Activity className="h-4 w-4 text-blue-500" />
            </div>
            <div className="text-3xl font-bold">
              {alpacaError ? (
                <span className="text-destructive text-lg">API Error</span>
              ) : alpacaAccount?.account ? (
                formatCurrency(parseFloat(alpacaAccount.account.buying_power || 0))
              ) : (
                <span className="text-muted-foreground">Loading...</span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {alpacaError ? 'Failed to fetch Capital data' : alpacaAccount?.account ? `Equity: ${formatCurrency(parseFloat(alpacaAccount.account.equity || 0))}` : 'Live stock trading balance'}
            </p>
            <div className="mt-3">
              <Button
                variant={capitalUseDemo ? "secondary" : "destructive"}
                size="sm"
                disabled={capitalModeUpdating}
                onClick={toggleCapitalMode}
              >
                {capitalModeUpdating ? "Switching..." : `Mode: ${capitalUseDemo ? "Demo" : "Live"} (Switch)`}
              </Button>
            </div>
          </Card>

          <Card className="p-6 bg-card border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Daily P&L</span>
              {dailyPnL >= 0 ? <TrendingUp className="h-4 w-4 text-accent" /> : <ArrowDownRight className="h-4 w-4 text-destructive" />}
            </div>
            <div className={`text-3xl font-bold ${formatProfitLoss(dailyPnL).colorClass}`}>
              {formatProfitLoss(dailyPnL).formatted}
            </div>
            <p className="text-xs text-muted-foreground mt-2">Today's performance</p>
          </Card>

          <Card className="p-6 bg-card border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Total P&L</span>
              {totalPnL >= 0 ? <TrendingUp className="h-4 w-4 text-accent" /> : <TrendingDown className="h-4 w-4 text-destructive" />}
            </div>
            <div className={`text-3xl font-bold ${formatProfitLoss(totalPnL).colorClass}`}>
              {formatProfitLoss(totalPnL).formatted}
            </div>
            <div className="text-xs text-muted-foreground mt-2">All time performance</div>
          </Card>
        </div>

        {/* AI Control Panel */}
        <Card className="p-4 sm:p-6 mb-8 bg-card border-border">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3 sm:gap-4">
              <div className={`w-12 h-12 sm:w-16 sm:h-16 rounded-2xl flex items-center justify-center ${aiEnabled ? 'gradient-accent shadow-profit' : 'bg-secondary'}`}>
                <Brain className="h-6 w-6 sm:h-8 sm:w-8" />
              </div>
              <div>
                <h3 className="text-xl sm:text-2xl font-bold mb-1">AI Trading Engine</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  {aiEnabled ? "AI is actively monitoring markets and executing trades" : "AI trading is currently disabled"}
                </p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              <Button 
                variant={aiEnabled ? "destructive" : "profit"} 
                size="lg"
                onClick={() => {
                  // Check minimum Alpaca balance before starting AI
                  if (!aiEnabled) {
                    const balance = alpacaAccount?.account ? parseFloat(alpacaAccount.account.equity || "0") : 0;
                    if (!Number.isFinite(balance) || balance < 5) {
                      toast({
                        title: "Insufficient Balance",
                        description: "You need at least $5.00 in your Alpaca account to start AI trading.",
                        variant: "destructive",
                      });
                      return;
                    }
                  }
                  setAiEnabled(!aiEnabled);
                }}
                className="gap-2"
              >
                <Power className="h-5 w-5" />
                {aiEnabled ? "Stop AI" : "Start AI"}
              </Button>
              
              <Button 
                variant="default"
                size="lg"
                onClick={async () => {
                  try {
                    const response = await apiClient.closeProfitableTrades();
                    
                    if (response.success) {
                      toast({
                        title: "Trades Closed",
                        description: response.message,
                        variant: "default",
                      });
                      // Refresh trades
                      refreshTrades();
                    } else {
                      toast({
                        title: "No Action Taken",
                        description: response.message,
                        variant: "default",
                      });
                    }
                  } catch (error: any) {
                    toast({
                      title: "Error",
                      description: error.message || "Failed to close trades",
                      variant: "destructive",
                    });
                  }
                }}
                className="gap-2 bg-blue-600 hover:bg-blue-700"
              >
                <TrendingUp className="h-5 w-5" />
                Close Profits
              </Button>
              
              <Button 
                variant="outline"
                size="lg"
                onClick={async () => {
                  try {
                    toast({
                      title: "Training ML Model",
                      description: "This may take a moment...",
                    });
                    
                    const response = await apiClient.trainMLModel();
                    
                    if (response.success) {
                      const accuracy = response.test_accuracy ? (response.test_accuracy * 100).toFixed(1) : 'N/A';
                      const trades = response.trades_count || 0;
                      toast({
                        title: "ML Model Trained",
                        description: `Accuracy: ${accuracy}% | Trades analyzed: ${trades}`,
                        variant: "default",
                      });
                    } else {
                      toast({
                        title: "Training Failed",
                        description: response.error || "Unable to train ML model",
                        variant: "destructive",
                      });
                    }
                  } catch (error: any) {
                    toast({
                      title: "Error",
                      description: error.message || "Failed to train ML model",
                      variant: "destructive",
                    });
                  }
                }}
                className="gap-2"
              >
                <Brain className="h-5 w-5" />
                Train ML
              </Button>
            </div>
          </div>

          {aiEnabled && (
            <div className="mt-6 pt-6 border-t border-border">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Daily Loss Limit</div>
                  <div className="flex items-center gap-2">
                    <Progress value={5} className="flex-1" />
                    <span className="text-sm font-semibold">5%</span>
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Position Size</div>
                  <div className="flex items-center gap-2">
                    <Progress value={40} className="flex-1" />
                    <span className="text-sm font-semibold">40%</span>
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Trade Frequency</div>
                  <div className="flex items-center gap-2">
                    <div className="text-lg font-bold text-accent">{formatNumber(tradeCount)}</div>
                    <span className="text-sm text-muted-foreground">trades today</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </Card>

        <PnLChart />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Active Positions */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="p-6 bg-card border-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold">Active Alpaca Positions</h3>
                {alpacaAccount?.positions && (
                  <Badge variant="secondary" className="text-xs">
                    {alpacaAccount.positions.count} position{alpacaAccount.positions.count !== 1 ? 's' : ''}
                  </Badge>
                )}
              </div>
              {!alpacaAccount || alpacaError ? (
                <p className="text-center text-muted-foreground py-8">
                  Unable to load Alpaca positions
                </p>
              ) : alpacaAccount.positions?.count === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  {aiEnabled ? "AI is analyzing markets..." : "No active positions"}
                </p>
              ) : (
                <div className="space-y-3">
                  {alpacaAccount.positions?.details?.map((pos: any, index: number) => {
                    const unrealizedPnL = pos.unrealized_pl || 0;
                    const unrealizedPnLPercent = pos.unrealized_plpc * 100 || 0;
                    const pnlFormatted = formatProfitLoss(unrealizedPnL);
                    
                    return (
                      <Card key={`${pos.symbol}-${index}`} className="p-4 bg-secondary border-border">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold">{pos.symbol}</span>
                              <Badge variant={pos.side === "long" ? "default" : "destructive"} className="text-xs">
                                {pos.side === "long" ? "BUY" : "SELL"}
                              </Badge>
                              <Badge variant="outline" className="text-xs">
                                Alpaca
                              </Badge>
                              {unrealizedPnLPercent > 0 && (
                                <Badge variant="default" className="text-xs bg-accent">
                                  +{unrealizedPnLPercent.toFixed(1)}%
                                </Badge>
                              )}
                            </div>
                            <div className="text-sm text-muted-foreground mt-1">
                              {formatNumber(pos.qty)} shares @ {formatCurrency(pos.avg_entry_price)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              Current: {formatCurrency(pos.current_price)} • Value: {formatCurrency(pos.market_value)}
                            </div>
                          </div>
                          <div className="text-right flex flex-col items-end gap-2">
                            {unrealizedPnL !== undefined && unrealizedPnL !== null && (
                              <div className={`flex items-center gap-1 font-bold ${pnlFormatted.colorClass}`}>
                                {unrealizedPnL >= 0 ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                                {pnlFormatted.formatted}
                              </div>
                            )}
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </Card>

            <Card className="p-6 bg-card border-border">
              <h3 className="text-xl font-bold mb-4">Recent Trades</h3>
              {displayRecentTrades.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  {aiEnabled ? "Waiting for trade executions..." : "No trades yet"}
                </p>
              ) : (
                <div className="space-y-2">
                  {displayRecentTrades.map((trade) => (
                    <div key={trade.id} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                      <div className="flex items-center gap-3">
                        <Badge variant={trade.side === "BUY" ? "default" : "outline"} className="w-14">
                          {trade.side}
                        </Badge>
                        <div>
                          <div className="font-semibold">{trade.symbol}</div>
                          <div className="text-xs text-muted-foreground">
                            {new Date((trade as any).closed_at || trade.created_at).toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold">{formatNumber(trade.quantity)} @ {formatCurrency(trade.entry_price)}</div>
                        {trade.pnl && (
                          <div className={`text-sm ${formatProfitLoss(trade.pnl).colorClass}`}>
                            {formatProfitLoss(trade.pnl).formatted}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* AI Signals */}
          <div className="space-y-6">
            <Card className="p-6 bg-card border-border">
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                AI Signals
              </h3>
              {!aiEnabled ? (
                <p className="text-center text-muted-foreground py-8">
                  Enable AI to see live trading signals
                </p>
              ) : displaySignals.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  Scanning markets for opportunities...
                </p>
              ) : (
                <div className="space-y-4">
                  {displaySignals.map((signal, i) => (
                  <Card key={i} className="p-4 bg-secondary border-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold">{signal.symbol}</span>
                      <Badge variant={signal.action === "BUY" ? "default" : "destructive"}>
                        {signal.action}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground mb-3">{signal.reason}</div>
                    <div className="flex items-center gap-2">
                      <Progress value={signal.confidence} className="flex-1 h-2" />
                      <span className="text-xs font-semibold text-primary">{signal.confidence}%</span>
                    </div>
                  </Card>
                  ))}
                </div>
              )}
            </Card>

            <Card className="p-6 bg-destructive/10 border-destructive/20">
              <div className="flex gap-3">
                <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-destructive mb-2">Risk Notice</h4>
                  <p className="text-sm text-muted-foreground">
                    Trading involves risk. Past performance does not guarantee future results. Only trade with money you can afford to lose.
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </div>
          </TabsContent>

          <TabsContent value="ai-agent" className="space-y-6">
            <AutonomousAgentControl />
          </TabsContent>

          <TabsContent value="pro-tools">
            <div className="space-y-6">
              {/* Performance Analytics */}
              <PerformanceAnalytics />
              
              {/* Risk Management and Watchlist */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <RiskManagementDashboard />
                <MarketWatchlist />
              </div>
              
              {/* Advanced Order Types */}
              <AdvancedOrderTypes 
                symbol="AAPL" 
                currentPrice={150.00}
                onOrderPlaced={() => refreshTrades()}
              />
            </div>
          </TabsContent>

          <TabsContent value="live-data">
            <LiveMarketData />
          </TabsContent>

        </Tabs>
      </div>
    </div>
  );
};

export default Dashboard;
