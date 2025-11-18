import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/ui/use-toast";

interface QuoteData {
  symbol: string;
  bid_price: number;
  ask_price: number;
  last_price: number;
  timestamp: string;
}

interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
  side: string;
}

export const useAlpacaData = () => {
  const [quotes, setQuotes] = useState<Record<string, QuoteData>>({});
  const [positions, setPositions] = useState<Position[]>([]);
  const [account, setAccount] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const getQuote = async (symbol: string, instrument_type: string = 'stock') => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('getQuote', { symbol, instrument_type });

      const quoteData = instrument_type === 'crypto' 
        ? data.quotes?.[symbol]
        : data.quote;

      if (quoteData) {
        setQuotes(prev => ({
          ...prev,
          [symbol]: {
            symbol,
            bid_price: quoteData.bp || quoteData.bid_price,
            ask_price: quoteData.ap || quoteData.ask_price,
            last_price: quoteData.ap || quoteData.ask_price,
            timestamp: quoteData.t || quoteData.timestamp,
          }
        }));
      }

      return quoteData;
    } catch (error) {
      console.error('Error fetching quote:', error);
      toast({
        title: "Error",
        description: "Failed to fetch market data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const getMultipleQuotes = async (symbols: string[]) => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('getQuotes', { symbols });

      const quotesData: Record<string, QuoteData> = {};
      Object.entries(data.quotes || {}).forEach(([symbol, quote]: [string, any]) => {
        quotesData[symbol] = {
          symbol,
          bid_price: quote.bp,
          ask_price: quote.ap,
          last_price: quote.ap,
          timestamp: quote.t,
        };
      });

      setQuotes(prev => ({ ...prev, ...quotesData }));
      return quotesData;
    } catch (error) {
      console.error('Error fetching quotes:', error);
      toast({
        title: "Error",
        description: "Failed to fetch market data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const placeOrder = async (
    symbol: string,
    qty: number,
    side: 'buy' | 'sell',
    instrument_type: string = 'stock'
  ) => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('placeOrder', { symbol, qty, side, instrument_type });

      toast({
        title: "Order Placed",
        description: `${side.toUpperCase()} ${qty} ${symbol}`,
      });

      return data;
    } catch (error) {
      console.error('Error placing order:', error);
      toast({
        title: "Error",
        description: "Failed to place order",
        variant: "destructive",
      });
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const fetchPositions = async () => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('getPositions');

      setPositions(data || []);
      return data;
    } catch (error) {
      console.error('Error fetching positions:', error);
      toast({
        title: "Error",
        description: "Failed to fetch positions",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchAccount = async () => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('getAccount');

      setAccount(data);
      return data;
    } catch (error) {
      console.error('Error fetching account:', error);
      toast({
        title: "Error",
        description: "Failed to fetch account data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return {
    quotes,
    positions,
    account,
    loading,
    getQuote,
    getMultipleQuotes,
    placeOrder,
    fetchPositions,
    fetchAccount,
  };
};
