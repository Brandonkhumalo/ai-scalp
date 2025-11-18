import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Bot, Play, StopCircle, TrendingUp, Globe } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";

interface AgentStatus {
  user: {
    autonomous_trading_enabled: boolean;
    ai_trading_enabled: boolean;
    forex_ai_trading_enabled: boolean;
    capital_ai_trading_enabled: boolean;
  };
  market_status: {
    timestamp_utc: string;
    open_markets: string[];
    markets_status: Record<string, {
      name: string;
      is_open: boolean;
      status: string;
      next_event: string;
      broker: string;
    }>;
  };
}

export function AutonomousAgentControl() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadAgentStatus();
    
    const interval = setInterval(loadAgentStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadAgentStatus = async () => {
    try {
      const response = await apiClient.get('/autonomous-agent/status/');
      setAgentStatus(response);
    } catch (error: any) {
      console.error('Failed to load agent status:', error);
      
      if (error.message?.includes('403') || error.message?.includes('Forbidden')) {
        setAgentStatus({
          user: {
            autonomous_trading_enabled: false,
            ai_trading_enabled: false,
            forex_ai_trading_enabled: false,
            capital_ai_trading_enabled: false,
          },
          market_status: {
            timestamp_utc: new Date().toISOString(),
            open_markets: [],
            markets_status: {},
          },
        });
        
        toast({
          title: "Authentication Issue",
          description: "Please try logging out and back in if controls don't load.",
          variant: "destructive",
        });
      }
    }
  };

  const toggleAutonomousAgent = async () => {
    setLoading(true);
    try {
      const newValue = !agentStatus?.user.autonomous_trading_enabled;
      await apiClient.post('/autonomous-agent/toggle/', {
        enabled: newValue
      });
      
      toast({
        title: newValue ? "Autonomous Agent Activated" : "Autonomous Agent Deactivated",
        description: newValue 
          ? "The 24/7 autonomous trading agent is now active across all markets" 
          : "Autonomous trading has been disabled. You can now use manual controls.",
      });
      
      await loadAgentStatus();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to toggle autonomous agent",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const triggerManualAI = async (broker: string, symbol: string, instrumentType: string) => {
    setLoading(true);
    try {
      const response = await apiClient.post('/manual-ai-trading/', {
        broker,
        symbol,
        instrument_type: instrumentType
      });
      
      if (response.success) {
        toast({
          title: "AI Trade Executed",
          description: `${response.message} - ${response.symbol}`,
        });
      } else {
        toast({
          title: "AI Trading Result",
          description: response.message,
          variant: response.success ? "default" : "destructive",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to execute AI trade",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  if (!agentStatus) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      </Card>
    );
  }

  const { user, market_status } = agentStatus;
  const openMarkets = market_status.open_markets || [];

  return (
    <div className="space-y-4">
      {/* Autonomous Agent Control */}
      <Card className="p-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${user.autonomous_trading_enabled ? 'bg-green-100' : 'bg-gray-100'}`}>
                <Bot className={`h-5 w-5 ${user.autonomous_trading_enabled ? 'text-green-600' : 'text-gray-600'}`} />
              </div>
              <div>
                <h3 className="font-semibold text-lg">24/7 Autonomous Trading Agent (Stocks Only)</h3>
                <p className="text-sm text-muted-foreground">
                  Automatically trades Alpaca stocks & Capital.com stocks across US/EU markets
                </p>
              </div>
            </div>
            <Switch
              checked={user.autonomous_trading_enabled}
              onCheckedChange={toggleAutonomousAgent}
              disabled={loading}
            />
          </div>

          {user.autonomous_trading_enabled && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <div className="flex items-start gap-2">
                <Globe className="h-5 w-5 text-blue-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900">Autonomous Agent Active (Stocks Only)</p>
                  <p className="text-xs text-blue-700 mt-1">
                    The agent automatically trades stocks when US/EU markets open. Manages Alpaca simulator 
                    and Capital.com stocks according to system parameters (8% daily loss limit). 
                    <strong> Forex trading is manual-only.</strong>
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Market Status */}
      <Card className="p-6">
        <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5" />
          Global Market Status
        </h3>
        <div className="space-y-3">
          {Object.entries(market_status.markets_status).map(([marketId, market]) => (
            <div key={marketId} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
              <div>
                <p className="font-medium">{market.name}</p>
                <p className="text-xs text-muted-foreground">{market.next_event}</p>
              </div>
              <Badge variant={market.is_open ? "default" : "secondary"}>
                {market.status}
              </Badge>
            </div>
          ))}
        </div>
        {openMarkets.length > 0 && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
            <p className="text-sm font-medium text-green-900">
              🟢 Active Markets: {openMarkets.join(', ')}
            </p>
          </div>
        )}
      </Card>

      {/* Manual AI Trading Controls */}
      <Card className="p-6">
        <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Play className="h-5 w-5" />
          Manual AI Trading
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          {user.autonomous_trading_enabled 
            ? "Autonomous agent handles stocks automatically. Forex trading is manual-only:"
            : "Autonomous agent is disabled. Trigger individual AI traders manually:"}
        </p>
        <div className="space-y-3">
          {!user.autonomous_trading_enabled && (
            <>
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-md">
                <div>
                  <p className="font-medium">Alpaca Stocks (Simulated)</p>
                  <p className="text-xs text-muted-foreground">Trade US stocks using ZimAI balance</p>
                </div>
                <Button
                  size="sm"
                  onClick={() => triggerManualAI('alpaca_sim', 'AAPL', 'stock')}
                  disabled={loading}
                >
                  <Play className="h-4 w-4 mr-2" />
                  Execute AI Trade
                </Button>
              </div>

              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-md">
                <div>
                  <p className="font-medium">Capital.com Stocks</p>
                  <p className="text-xs text-muted-foreground">Trade US/EU stocks on Capital.com</p>
                </div>
                <Button
                  size="sm"
                  onClick={() => triggerManualAI('capital_stock', 'AAPL', 'stock')}
                  disabled={loading}
                >
                  <Play className="h-4 w-4 mr-2" />
                  Execute AI Trade
                </Button>
              </div>
            </>
          )}
          
          <div className="flex items-center justify-between p-4 bg-amber-50 border border-amber-200 rounded-md">
            <div>
              <p className="font-medium">Capital.com Forex (Manual Only)</p>
              <p className="text-xs text-muted-foreground">Trade 4 authorized forex pairs - Not in autonomous agent</p>
            </div>
            <Button
              size="sm"
              onClick={() => triggerManualAI('capital_forex', 'EUR/USD', 'forex')}
              disabled={loading}
            >
              <Play className="h-4 w-4 mr-2" />
              Execute AI Trade
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
