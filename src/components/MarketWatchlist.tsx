import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { 
  TrendingUp, 
  TrendingDown, 
  Star,
  Plus,
  Trash2,
  Activity,
  Zap
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatPercentage, formatChange } from "@/lib/formatters";

interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  lastUpdate: Date;
}

const DEFAULT_SYMBOLS = [
  { symbol: "AAPL", name: "Apple Inc." },
  { symbol: "GOOGL", name: "Alphabet Inc." },
  { symbol: "TSLA", name: "Tesla Inc." },
  { symbol: "MSFT", name: "Microsoft" },
  { symbol: "AMZN", name: "Amazon" },
  { symbol: "NVDA", name: "NVIDIA" },
  { symbol: "META", name: "Meta Platforms" },
  { symbol: "NFLX", name: "Netflix" }
];

export const MarketWatchlist = ({ onQuickTrade }: { onQuickTrade?: (symbol: string, price: number) => void }) => {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [newSymbol, setNewSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [userSymbols, setUserSymbols] = useState<Array<{ symbol: string; name: string }>>(DEFAULT_SYMBOLS);

  useEffect(() => {
    loadWatchlist();
    
    // Update prices every 5 seconds
    const interval = setInterval(loadWatchlist, 5000);
    return () => clearInterval(interval);
  }, [userSymbols]);

  const loadWatchlist = async () => {
    try {
      const items = await Promise.all(
        userSymbols.map(async ({ symbol, name }) => {
          try {
            const instrumentType = 'stock';
            
            const data = await apiClient.alpacaMarketData('getSnapshot', { 
              symbol, 
              instrument_type: instrumentType 
            });

            const currentPrice = data?.latestQuote?.ap || data?.quote?.ap || 0;
            const prevClose = data?.prevDailyBar?.c || currentPrice;
            const change = currentPrice - prevClose;
            const changePercent = prevClose > 0 ? (change / prevClose) * 100 : 0;
            const volume = data?.dailyBar?.v || data?.prevDailyBar?.v || 0;

            return {
              symbol,
              name,
              price: currentPrice,
              change,
              changePercent,
              volume,
              lastUpdate: new Date()
            };
          } catch (error) {
            console.error(`Error loading ${symbol}:`, error);
            return {
              symbol,
              name,
              price: 0,
              change: 0,
              changePercent: 0,
              volume: 0,
              lastUpdate: new Date()
            };
          }
        })
      );

      setWatchlist(items.filter(item => item.price > 0));
    } catch (error) {
      console.error('Error loading watchlist:', error);
    }
  };

  const addSymbol = async () => {
    if (!newSymbol.trim()) return;
    
    setLoading(true);
    try {
      const symbolToAdd = newSymbol.trim().toUpperCase();
      
      // Check if symbol already exists
      if (userSymbols.some(s => s.symbol === symbolToAdd)) {
        setNewSymbol("");
        setLoading(false);
        return;
      }
      
      // Add to user symbols list
      setUserSymbols(prev => [...prev, { symbol: symbolToAdd, name: symbolToAdd }]);
      setNewSymbol("");
    } catch (error) {
      console.error('Error adding symbol:', error);
    } finally {
      setLoading(false);
    }
  };

  const removeSymbol = (symbol: string) => {
    setUserSymbols(prev => prev.filter(item => item.symbol !== symbol));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Star className="h-5 w-5" />
          Market Watchlist
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Add Symbol */}
        <div className="flex gap-2 mb-4">
          <Input
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
            placeholder="Add symbol (e.g., NVDA)"
            onKeyPress={(e) => e.key === 'Enter' && addSymbol()}
          />
          <Button 
            onClick={addSymbol} 
            disabled={loading || !newSymbol.trim()}
            size="icon"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {/* Watchlist Items */}
        <div className="space-y-2">
          {watchlist.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              Loading watchlist...
            </p>
          ) : (
            watchlist.map((item) => (
              <div
                key={item.symbol}
                className="flex items-center justify-between p-3 bg-secondary rounded-lg hover:bg-accent/5 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold">{item.symbol}</span>
                    <span className="text-xs text-muted-foreground">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-lg font-bold">
                      {formatCurrency(item.price)}
                    </span>
                    <div className={`flex items-center gap-1 text-sm ${item.change >= 0 ? 'text-accent' : 'text-destructive'}`}>
                      {item.change >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      <span>
                        {item.change >= 0 ? '+' : ''}{formatCurrency(item.change)} ({formatPercentage(item.changePercent, 2)})
                      </span>
                    </div>
                  </div>
                  {item.volume > 0 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      Vol: {(item.volume / 1000000).toFixed(2)}M
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {onQuickTrade && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onQuickTrade(item.symbol, item.price)}
                      className="gap-1"
                    >
                      <Zap className="h-3 w-3" />
                      Trade
                    </Button>
                  )}
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => removeSymbol(item.symbol)}
                    className="h-8 w-8"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Last Update */}
        {watchlist.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Activity className="h-3 w-3" />
                <span>Live updates every 5 seconds</span>
              </div>
              <span>
                Last: {watchlist[0]?.lastUpdate.toLocaleTimeString()}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
