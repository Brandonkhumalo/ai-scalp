import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiClient } from '../services/api';
import { useAuth } from './AuthContext';

interface Trade {
  id: number;
  symbol: string;
  side: 'BUY' | 'SELL';
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

interface TradingContextType {
  aiEnabled: boolean;
  setAiEnabled: (enabled: boolean) => void;
  positions: Trade[];
  recentTrades: Trade[];
  dailyPnL: number;
  totalPnL: number;
  tradeCount: number;
  alpacaEquity: number;
  alpacaUnrealizedPnL: number;
  refreshTrades: () => Promise<void>;
  isLoading: boolean;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

export function TradingProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  const [aiEnabled, setAiEnabledState] = useState(false);
  const [positions, setPositions] = useState<Trade[]>([]);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [dailyPnL, setDailyPnL] = useState(0);
  const [totalPnL, setTotalPnL] = useState(0);
  const [tradeCount, setTradeCount] = useState(0);
  const [alpacaEquity, setAlpacaEquity] = useState(0);
  const [alpacaUnrealizedPnL, setAlpacaUnrealizedPnL] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setAiEnabledState(user.ai_trading_enabled || false);
    }
  }, [user]);

  const setAiEnabled = useCallback(async (enabled: boolean) => {
    try {
      await apiClient.toggleAITrading(enabled);
      setAiEnabledState(enabled);
    } catch (error) {
      console.error('Error toggling AI trading:', error);
      throw error;
    }
  }, []);

  const refreshTrades = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);

    try {
      let alpacaData = null;
      try {
        alpacaData = await apiClient.getAlpacaAccount();
        if (alpacaData) {
          const currentEquity = alpacaData.account?.equity || 0;
          const lastEquity = alpacaData.account?.last_equity || currentEquity;

          const unrealizedPnL = alpacaData.positions?.details?.reduce(
            (sum: number, pos: any) => sum + (pos.unrealized_pl || 0),
            0
          ) || 0;

          let totalRealizedPnL = 0;
          try {
            const analytics = await apiClient.getPerformanceAnalytics();
            totalRealizedPnL = analytics.netPnL || 0;
          } catch (err) {
            console.error('Error fetching analytics:', err);
          }

          const totalPnLValue = totalRealizedPnL + unrealizedPnL;
          const dailyPnLValue = currentEquity - lastEquity;

          setAlpacaEquity(currentEquity);
          setAlpacaUnrealizedPnL(unrealizedPnL);
          setTotalPnL(totalPnLValue);
          setDailyPnL(dailyPnLValue);
        }
      } catch (error) {
        console.error('Error fetching Alpaca account:', error);
      }

      const tradesData = await apiClient.getTrades();
      const openPositions = tradesData.filter((t: any) => t.status === 'open');
      setPositions(openPositions);

      const allClosedTrades = tradesData.filter((t: any) => t.status === 'closed');
      const recentClosedTrades = [...allClosedTrades]
        .sort((a: any, b: any) => 
          new Date(b.closed_at || b.created_at).getTime() - new Date(a.closed_at || a.created_at).getTime()
        )
        .slice(0, 10);
      setRecentTrades(recentClosedTrades);
      setTradeCount(tradesData.length);
    } catch (error) {
      console.error('Error refreshing trades:', error);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      refreshTrades();
      const interval = setInterval(refreshTrades, 5000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, refreshTrades]);

  return (
    <TradingContext.Provider
      value={{
        aiEnabled,
        setAiEnabled,
        positions,
        recentTrades,
        dailyPnL,
        totalPnL,
        tradeCount,
        alpacaEquity,
        alpacaUnrealizedPnL,
        refreshTrades,
        isLoading,
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
