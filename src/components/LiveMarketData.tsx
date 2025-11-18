import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Brain, TrendingUp, TrendingDown, BarChart3, Zap, ArrowUpRight, ArrowDownRight, Activity } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { useTrading } from "@/contexts/TradingContext";
import { formatCurrency, formatPrice, formatPercentage, formatProfitLoss } from "@/lib/formatters";

export const LiveMarketData = () => {
  const { toast } = useToast();
  const { aiEnabled, setAiEnabled, positions } = useTrading();
  const [symbol, setSymbol] = useState("AAPL");
  const [instrumentType, setInstrumentType] = useState<'stock' | 'option' | 'forex'>('stock');
  const [marketData, setMarketData] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [orderBook, setOrderBook] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [autoTrading, setAutoTrading] = useState(false);

  // International stock exchanges
  const exchanges = [
    { value: 'NASDAQ', label: 'NASDAQ (US)' },
    { value: 'NYSE', label: 'NYSE (US)' },
    { value: 'LSE', label: 'London Stock Exchange' },
    { value: 'TSE', label: 'Tokyo Stock Exchange' },
    { value: 'HKEX', label: 'Hong Kong Stock Exchange' },
  ];

  // Disabled - no API polling for market data
  // useEffect(() => {
  //   if (symbol) {
  //     loadMarketData();
  //     
  //     // Set up real-time polling for market data and order book
  //     const interval = setInterval(() => {
  //       loadMarketData();
  //     }, 3000); // Update every 3 seconds
  //     
  //     return () => clearInterval(interval);
  //   }
  // }, [symbol, instrumentType]);

  // Disabled - no sentiment analysis polling
  // useEffect(() => {
  //   if (aiEnabled) {
  //     analyzeSentiment();
  //     
  //     // Poll sentiment analysis every 5 seconds when AI is enabled
  //     const sentimentInterval = setInterval(() => {
  //       analyzeSentiment();
  //     }, 5000);
  //     
  //     return () => clearInterval(sentimentInterval);
  //   }
  // }, [aiEnabled, symbol, instrumentType]);

  useEffect(() => {
    setAutoTrading(aiEnabled);
  }, [aiEnabled]);

  const loadMarketData = async () => {
    try {
      setLoading(true);
      
      // Get market snapshot
      const snapshot = await apiClient.alpacaMarketData('getSnapshot', { 
        symbol, 
        instrument_type: instrumentType 
      });
      setMarketData(snapshot);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const analyzeSentiment = async () => {
    try {
      const analysis = await apiClient.analyzeSentiment(symbol, instrumentType);
      setSentiment(analysis);
    } catch (error: any) {
      console.error('Sentiment analysis error:', error);
    }
  };

  const handleAITrade = async () => {
    try {
      setLoading(true);
      const result = await apiClient.executeAITrade(symbol, instrumentType);
      
      if (result.success) {
        toast({
          title: "AI Trade Executed",
          description: `${result.side} ${result.quantity} ${result.symbol} at $${result.price}`,
        });
        loadMarketData();
      }
    } catch (error: any) {
      toast({
        title: "Trade Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAutoTrading = async () => {
    if (!autoTrading) {
      setAutoTrading(true);
      setAiEnabled(true);
      toast({
        title: "Auto Trading Started",
        description: "AI is now monitoring markets and generating trades",
      });
    } else {
      setAutoTrading(false);
      setAiEnabled(false);
      toast({
        title: "Auto Trading Stopped",
        description: "AI trading has been disabled",
      });
    }
  };

  const currentPrice = marketData?.latestQuote?.ap || marketData?.quote?.ap || 0;
  const bidPrice = marketData?.latestQuote?.bp || marketData?.quote?.bp || 0;
  const askPrice = marketData?.latestQuote?.ap || marketData?.quote?.ap || 0;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Live Market Data & AI Trading
          </CardTitle>
          <CardDescription>Real-time market data with AI-powered trading signals</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Instrument Type</Label>
              <Select value={instrumentType} onValueChange={(v: any) => setInstrumentType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stock">Stocks</SelectItem>
                  <SelectItem value="option">Options</SelectItem>
                  <SelectItem value="forex">Forex</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {instrumentType === 'stock' && (
              <div className="space-y-2">
                <Label>Exchange</Label>
                <Select defaultValue="NASDAQ">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {exchanges.map(ex => (
                      <SelectItem key={ex.value} value={ex.value}>{ex.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>Symbol</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
              />
            </div>
          </div>

          {currentPrice > 0 && (
            <div className="grid grid-cols-3 gap-4 mt-6">
              <Card className="p-4 bg-secondary">
                <div className="text-sm text-muted-foreground">Current Price</div>
                <div className="text-2xl font-bold">{formatPrice(currentPrice)}</div>
              </Card>
              <Card className="p-4 bg-secondary">
                <div className="text-sm text-muted-foreground">Bid</div>
                <div className="text-2xl font-bold text-accent">{formatPrice(bidPrice)}</div>
              </Card>
              <Card className="p-4 bg-secondary">
                <div className="text-sm text-muted-foreground">Ask</div>
                <div className="text-2xl font-bold text-destructive">{formatPrice(askPrice)}</div>
              </Card>
            </div>
          )}

          {/* AI Trading Panel */}
          <Card className="p-4 bg-gradient-to-br from-purple-500/10 to-blue-500/10 border-purple-500/20">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Brain className={`h-6 w-6 ${aiEnabled ? 'text-purple-500 animate-pulse' : 'text-gray-500'}`} />
                <div>
                  <h3 className="font-bold">AI Trading Engine</h3>
                  <p className="text-xs text-muted-foreground">
                    {aiEnabled ? 'Active - Analyzing markets' : 'Inactive'}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant={aiEnabled ? "destructive" : "default"}
                  size="sm"
                  onClick={() => setAiEnabled(!aiEnabled)}
                >
                  {aiEnabled ? 'Disable AI' : 'Enable AI'}
                </Button>
                <Button
                  variant={autoTrading ? "destructive" : "default"}
                  size="sm"
                  onClick={handleAutoTrading}
                  disabled={!aiEnabled}
                >
                  <Zap className="h-4 w-4 mr-1" />
                  {autoTrading ? 'Stop Auto' : 'Auto Trade'}
                </Button>
              </div>
            </div>

            {sentiment && aiEnabled && (
              <div className="space-y-3 mt-4 pt-4 border-t border-purple-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Signal</span>
                  <Badge variant={sentiment.signal === 'BUY' ? 'default' : 'destructive'}>
                    {sentiment.signal || 'NEUTRAL'}
                  </Badge>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>AI Confidence</span>
                    <span className="font-semibold">{formatPercentage(sentiment.confidence, 0)}</span>
                  </div>
                  <Progress value={sentiment.confidence || 0} className="h-2" />
                </div>
                <div className="flex items-center gap-2 text-sm">
                  {sentiment.momentum > 0 ? (
                    <TrendingUp className="h-4 w-4 text-accent" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-destructive" />
                  )}
                  <span>Momentum: {formatPercentage(sentiment.momentum)}</span>
                </div>
                {sentiment.signal && (
                  <Button 
                    onClick={handleAITrade} 
                    disabled={loading}
                    className="w-full mt-2"
                    variant="default"
                  >
                    Execute AI Trade
                  </Button>
                )}
              </div>
            )}
          </Card>

          {/* Active Trades */}
          {positions.length > 0 && (
            <Card className="p-4">
              <h3 className="font-bold mb-3">Active AI Trades</h3>
              <div className="space-y-2">
                {positions.slice(0, 5).map((pos: any) => {
                  const currentPnL = pos.profit_loss !== undefined ? pos.profit_loss : pos.pnl;
                  const pnlFormatted = formatProfitLoss(currentPnL);
                  return (
                    <div key={pos.id} className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                      <div className="flex items-center gap-3">
                        <Badge variant={pos.side === "BUY" || pos.side === "buy" ? "default" : "destructive"}>
                          {typeof pos.side === 'string' ? pos.side.toUpperCase() : pos.side}
                        </Badge>
                        <div>
                          <div className="font-semibold">{pos.symbol}</div>
                          <div className="text-xs text-muted-foreground">
                            {pos.quantity} @ {formatPrice(pos.entry_price)}
                          </div>
                        </div>
                      </div>
                      {currentPnL !== undefined && currentPnL !== null && (
                        <div className={`flex items-center gap-1 font-bold ${pnlFormatted.colorClass}`}>
                          {currentPnL >= 0 ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                          {pnlFormatted.formatted}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

        </CardContent>
      </Card>
    </div>
  );
};
