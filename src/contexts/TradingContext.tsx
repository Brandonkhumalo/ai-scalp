import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api-client';

interface Trade {
  id: number;
  symbol: string;
  side: "BUY" | "SELL";
  status: string;
  quantity: number;
  entry_price: number;
  current_price?: number;
  pnl?: number;
  profit_loss?: number;
  confidence?: number;
  broker?: string;
  created_at: string;
}

interface Signal {
  symbol: string;
  action: "BUY" | "SELL";
  confidence: number;
  reason: string;
}

interface TradingContextType {
  aiEnabled: boolean;
  setAiEnabled: (enabled: boolean) => void;
  positions: Trade[];
  recentTrades: Trade[];
  signals: Signal[];
  dailyPnL: number;
  totalPnL: number;
  tradeCount: number;
  alpacaEquity: number;
  alpacaUnrealizedPnL: number;
  refreshTrades: () => Promise<void>;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

export function TradingProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [aiEnabled, setAiEnabledState] = useState(false);
  const [positions, setPositions] = useState<Trade[]>([]);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [dailyPnL, setDailyPnL] = useState(0);
  const [totalPnL, setTotalPnL] = useState(0);
  const [tradeCount, setTradeCount] = useState(0);
  const [alpacaEquity, setAlpacaEquity] = useState(0);
  const [alpacaUnrealizedPnL, setAlpacaUnrealizedPnL] = useState(0);

  useEffect(() => {
    const loadAIState = async () => {
      if (!apiClient.isAuthenticated()) {
        setAiEnabledState(false);
        return;
      }
      
      const isLandingPage = location.pathname === '/' || location.pathname === '/auth';
      if (isLandingPage) return;
      
      try {
        const userData = await apiClient.getMe();
        setAiEnabledState(userData.user.ai_trading_enabled || false);
        
        const cachedUser = apiClient.getCachedUser();
        if (cachedUser) {
          cachedUser.ai_trading_enabled = userData.user.ai_trading_enabled;
          localStorage.setItem('user', JSON.stringify(cachedUser));
        }
      } catch (error) {
        console.error('Error loading AI state:', error);
        
        const cachedUser = apiClient.getCachedUser();
        if (cachedUser && cachedUser.ai_trading_enabled !== undefined) {
          setAiEnabledState(cachedUser.ai_trading_enabled);
        }
      }
    };

    loadAIState();
  }, [location.pathname]);

  const setAiEnabled = useCallback(async (enabled: boolean) => {
    try {
      await apiClient.toggleAITrading(enabled);
      setAiEnabledState(enabled);
    } catch (error) {
      console.error('Error toggling AI trading:', error);
    }
  }, []);

  const refreshTrades = useCallback(async () => {
    if (!apiClient.isAuthenticated()) return;

    try {
      // Fetch Alpaca account data for P&L calculations
      let alpacaData = null;
      try {
        alpacaData = await apiClient.get('/alpaca-account/');
        if (alpacaData) {
          const currentEquity = alpacaData.account?.equity || 0;
          const lastEquity = alpacaData.account?.last_equity || 100000; // Default starting balance
          
          // Calculate total unrealized P&L from positions
          const unrealizedPnL = alpacaData.positions?.details?.reduce(
            (sum: number, pos: any) => sum + (pos.unrealized_pl || 0), 
            0
          ) || 0;
          
          // Total P&L = current equity - starting balance (last_equity represents previous day)
          // For a more accurate all-time P&L, we use current equity - 100000 (assumed starting balance)
          const totalPnL = currentEquity - 100000;
          
          // Daily P&L = current equity - last equity (previous day's closing)
          const dailyPnL = currentEquity - lastEquity;
          
          setAlpacaEquity(currentEquity);
          setAlpacaUnrealizedPnL(unrealizedPnL);
          setTotalPnL(totalPnL);
          setDailyPnL(dailyPnL);
        }
      } catch (error) {
        console.error('Error fetching Alpaca account:', error);
      }

      const tradesData = await apiClient.getTrades();
      const openPositions = tradesData.filter((t: any) => t.status === "open");
      setPositions(openPositions);

      // Get ALL closed trades for display
      const allClosedTrades = tradesData.filter((t: any) => t.status === "closed");

      // Get 10 most recent closed trades for display (create copy to avoid mutation)
      const recentClosedTrades = [...allClosedTrades]
        .sort((a: any, b: any) => new Date(b.closed_at || b.created_at).getTime() - new Date(a.closed_at || a.created_at).getTime())
        .slice(0, 10);
      setRecentTrades(recentClosedTrades);

      // Set trade count from total number of trades
      setTradeCount(tradesData.length);
    } catch (error) {
      if (!apiClient.isAuthenticated()) {
        return;
      }
    }
  }, []);

  // Refresh trades when AI is disabled to show closed positions
  useEffect(() => {
    if (!aiEnabled && apiClient.isAuthenticated()) {
      const timeoutId = setTimeout(() => {
        refreshTrades();
      }, 500); // Small delay to allow backend to complete closing trades
      return () => clearTimeout(timeoutId);
    }
  }, [aiEnabled, refreshTrades]);

  useEffect(() => {
    const isLandingPage = location.pathname === '/' || location.pathname === '/auth';
    
    if (isLandingPage || !apiClient.isAuthenticated()) return;

    // Always load real trades from database on mount
    const loadInitialData = async () => {
      if (!apiClient.isAuthenticated()) return;
      await refreshTrades();
    };

    loadInitialData();

    // Refresh trades periodically to sync with backend (every 3 seconds for real-time updates)
    // The AI Trading Scheduler (backend) handles all trading - frontend only displays data
    const syncInterval = setInterval(() => {
      if (apiClient.isAuthenticated()) {
        refreshTrades();
      }
    }, 3000);

    return () => {
      clearInterval(syncInterval);
    };
  }, [aiEnabled, location.pathname, refreshTrades]);

  return (
    <TradingContext.Provider
      value={{
        aiEnabled,
        setAiEnabled,
        positions,
        recentTrades,
        signals,
        dailyPnL,
        totalPnL,
        tradeCount,
        alpacaEquity,
        alpacaUnrealizedPnL,
        refreshTrades
      }}
    >
      {children}
    </TradingContext.Provider>
  );
}

export function useTrading() {
  const context = useContext(TradingContext);
  if (context === undefined) {
    throw new Error('useTrading must be used within a TradingProvider');
  }
  return context;
}
