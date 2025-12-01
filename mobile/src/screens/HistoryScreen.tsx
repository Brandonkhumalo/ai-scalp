import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { apiClient } from '../services/api';
import { formatCurrency, formatProfitLoss, formatNumber, formatDate } from '../utils/formatters';

interface Trade {
  id: number;
  symbol: string;
  side: string;
  status: string;
  quantity: number;
  entry_price: number;
  exit_price?: number;
  profit_loss?: number;
  created_at: string;
  closed_at?: string;
}

export function HistoryScreen() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadTrades = useCallback(async () => {
    try {
      const data = await apiClient.getTrades();
      const closedTrades = data
        .filter((t: Trade) => t.status === 'closed')
        .sort((a: Trade, b: Trade) => 
          new Date(b.closed_at || b.created_at).getTime() - 
          new Date(a.closed_at || a.created_at).getTime()
        );
      setTrades(closedTrades);
    } catch (error) {
      console.error('Error loading trades:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTrades();
  }, [loadTrades]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTrades();
    setRefreshing(false);
  }, [loadTrades]);

  const totalProfitLoss = trades.reduce((sum, t) => sum + (t.profit_loss || 0), 0);
  const winningTrades = trades.filter((t) => (t.profit_loss || 0) > 0);
  const losingTrades = trades.filter((t) => (t.profit_loss || 0) < 0);
  const winRate = trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0;

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#22c55e" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor="#22c55e"
        />
      }
    >
      <Text style={styles.title}>Trade History</Text>

      <View style={styles.summaryGrid}>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Total P&L</Text>
          <Text style={[
            styles.summaryValue,
            totalProfitLoss >= 0 ? styles.profit : styles.loss
          ]}>
            {formatProfitLoss(totalProfitLoss).formatted}
          </Text>
        </View>

        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Win Rate</Text>
          <Text style={styles.summaryValue}>{winRate.toFixed(1)}%</Text>
        </View>

        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Total Trades</Text>
          <Text style={styles.summaryValue}>{trades.length}</Text>
        </View>

        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Wins / Losses</Text>
          <Text style={styles.summaryValue}>
            <Text style={styles.profit}>{winningTrades.length}</Text>
            <Text style={styles.textMuted}> / </Text>
            <Text style={styles.loss}>{losingTrades.length}</Text>
          </Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Recent Trades</Text>

      {trades.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No closed trades yet</Text>
        </View>
      ) : (
        trades.map((trade) => {
          const pnl = trade.profit_loss || 0;
          const pnlFormatted = formatProfitLoss(pnl);

          return (
            <View key={trade.id} style={styles.tradeCard}>
              <View style={styles.tradeHeader}>
                <View style={styles.tradeSymbolRow}>
                  <Text style={styles.tradeSymbol}>{trade.symbol}</Text>
                  <View style={[
                    styles.tradeBadge,
                    trade.side.toUpperCase() === 'BUY' ? styles.badgeBuy : styles.badgeSell
                  ]}>
                    <Text style={styles.badgeText}>{trade.side.toUpperCase()}</Text>
                  </View>
                </View>
                <Text style={[
                  styles.tradePnL,
                  pnlFormatted.isProfit ? styles.profit : styles.loss
                ]}>
                  {pnlFormatted.formatted}
                </Text>
              </View>

              <View style={styles.tradeDetails}>
                <View style={styles.tradeRow}>
                  <Text style={styles.tradeLabel}>Quantity</Text>
                  <Text style={styles.tradeValue}>{formatNumber(trade.quantity)} shares</Text>
                </View>
                <View style={styles.tradeRow}>
                  <Text style={styles.tradeLabel}>Entry</Text>
                  <Text style={styles.tradeValue}>{formatCurrency(trade.entry_price)}</Text>
                </View>
                {trade.exit_price && (
                  <View style={styles.tradeRow}>
                    <Text style={styles.tradeLabel}>Exit</Text>
                    <Text style={styles.tradeValue}>{formatCurrency(trade.exit_price)}</Text>
                  </View>
                )}
                <View style={styles.tradeRow}>
                  <Text style={styles.tradeLabel}>Closed</Text>
                  <Text style={styles.tradeValue}>
                    {formatDate(trade.closed_at || trade.created_at)}
                  </Text>
                </View>
              </View>
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  content: {
    padding: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0f0f0f',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 24,
  },
  summaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  summaryCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    flex: 1,
    minWidth: '45%',
    borderWidth: 1,
    borderColor: '#333',
  },
  summaryLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  profit: {
    color: '#22c55e',
  },
  loss: {
    color: '#ef4444',
  },
  textMuted: {
    color: '#888',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 12,
  },
  emptyState: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 32,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#333',
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
  },
  tradeCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#333',
  },
  tradeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
  },
  tradeSymbolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  tradeSymbol: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  tradeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  badgeBuy: {
    backgroundColor: '#22c55e33',
  },
  badgeSell: {
    backgroundColor: '#ef444433',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  tradePnL: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  tradeDetails: {
    gap: 8,
  },
  tradeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  tradeLabel: {
    fontSize: 14,
    color: '#888',
  },
  tradeValue: {
    fontSize: 14,
    color: '#fff',
  },
});
