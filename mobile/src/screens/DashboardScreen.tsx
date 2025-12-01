import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useAuth } from '../contexts/AuthContext';
import { useTrading } from '../contexts/TradingContext';
import { apiClient } from '../services/api';
import { formatCurrency, formatProfitLoss, formatNumber } from '../utils/formatters';

export function DashboardScreen() {
  const { user } = useAuth();
  const {
    aiEnabled,
    setAiEnabled,
    positions,
    dailyPnL,
    totalPnL,
    tradeCount,
    alpacaEquity,
    alpacaUnrealizedPnL,
    refreshTrades,
    isLoading,
  } = useTrading();

  const [alpacaAccount, setAlpacaAccount] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [togglingAI, setTogglingAI] = useState(false);
  const [closingTrades, setClosingTrades] = useState(false);

  const loadAlpacaAccount = useCallback(async () => {
    try {
      const data = await apiClient.getAlpacaAccount();
      setAlpacaAccount(data);
    } catch (error) {
      console.error('Error loading Alpaca account:', error);
    }
  }, []);

  useEffect(() => {
    loadAlpacaAccount();
  }, [loadAlpacaAccount]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refreshTrades(), loadAlpacaAccount()]);
    setRefreshing(false);
  }, [refreshTrades, loadAlpacaAccount]);

  const handleToggleAI = async () => {
    if (togglingAI) return;

    if (!aiEnabled) {
      const equity = alpacaAccount?.account?.equity || 0;
      if (parseFloat(equity) < 5) {
        Alert.alert(
          'Insufficient Balance',
          'You need at least $5.00 in your Alpaca account to start AI trading.'
        );
        return;
      }
    }

    setTogglingAI(true);
    try {
      await setAiEnabled(!aiEnabled);
      Alert.alert(
        'Success',
        aiEnabled ? 'AI Trading has been stopped' : 'AI Trading has been started'
      );
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to toggle AI trading');
    } finally {
      setTogglingAI(false);
    }
  };

  const handleCloseProfitableTrades = async () => {
    if (closingTrades) return;

    setClosingTrades(true);
    try {
      const response = await apiClient.closeProfitableTrades();
      Alert.alert('Result', response.message || 'Operation completed');
      await refreshTrades();
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to close trades');
    } finally {
      setClosingTrades(false);
    }
  };

  const dailyPnLFormatted = formatProfitLoss(dailyPnL);
  const totalPnLFormatted = formatProfitLoss(totalPnL);

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
      <View style={styles.header}>
        <Text style={styles.greeting}>Welcome back,</Text>
        <Text style={styles.name}>{user?.full_name || user?.email}</Text>
      </View>

      <View style={styles.statsGrid}>
        <View style={[styles.statCard, styles.statCardPrimary]}>
          <Text style={styles.statLabel}>Alpaca Balance</Text>
          <Text style={styles.statValue}>
            {formatCurrency(alpacaAccount?.account?.buying_power || 0)}
          </Text>
          <Text style={styles.statSubtext}>
            Equity: {formatCurrency(alpacaAccount?.account?.equity || 0)}
          </Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Daily P&L</Text>
          <Text style={[styles.statValue, dailyPnLFormatted.isProfit ? styles.profit : styles.loss]}>
            {dailyPnLFormatted.formatted}
          </Text>
          <Text style={styles.statSubtext}>Today's performance</Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Total P&L</Text>
          <Text style={[styles.statValue, totalPnLFormatted.isProfit ? styles.profit : styles.loss]}>
            {totalPnLFormatted.formatted}
          </Text>
          <Text style={styles.statSubtext}>All time</Text>
        </View>
      </View>

      <View style={styles.aiControl}>
        <View style={styles.aiHeader}>
          <View style={[styles.aiIcon, aiEnabled && styles.aiIconActive]}>
            <Text style={styles.aiIconText}>AI</Text>
          </View>
          <View style={styles.aiInfo}>
            <Text style={styles.aiTitle}>AI Trading Engine</Text>
            <Text style={styles.aiSubtitle}>
              {aiEnabled
                ? 'Actively monitoring and trading'
                : 'Currently disabled'}
            </Text>
          </View>
        </View>

        <View style={styles.aiButtons}>
          <TouchableOpacity
            style={[
              styles.aiButton,
              aiEnabled ? styles.aiButtonStop : styles.aiButtonStart,
              togglingAI && styles.buttonDisabled,
            ]}
            onPress={handleToggleAI}
            disabled={togglingAI}
          >
            {togglingAI ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.aiButtonText}>
                {aiEnabled ? 'Stop AI' : 'Start AI'}
              </Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.closeButton, closingTrades && styles.buttonDisabled]}
            onPress={handleCloseProfitableTrades}
            disabled={closingTrades}
          >
            {closingTrades ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.closeButtonText}>Close Profits</Text>
            )}
          </TouchableOpacity>
        </View>

        {aiEnabled && (
          <View style={styles.aiStats}>
            <View style={styles.aiStatItem}>
              <Text style={styles.aiStatLabel}>Trade Count</Text>
              <Text style={styles.aiStatValue}>{formatNumber(tradeCount)}</Text>
            </View>
            <View style={styles.aiStatItem}>
              <Text style={styles.aiStatLabel}>Unrealized P&L</Text>
              <Text style={[
                styles.aiStatValue,
                alpacaUnrealizedPnL >= 0 ? styles.profit : styles.loss
              ]}>
                {formatCurrency(alpacaUnrealizedPnL)}
              </Text>
            </View>
          </View>
        )}
      </View>

      <View style={styles.positionsSection}>
        <Text style={styles.sectionTitle}>Active Positions</Text>
        {isLoading ? (
          <ActivityIndicator color="#22c55e" style={styles.loader} />
        ) : alpacaAccount?.positions?.count === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>
              {aiEnabled ? 'AI is analyzing markets...' : 'No active positions'}
            </Text>
          </View>
        ) : (
          alpacaAccount?.positions?.details?.map((pos: any, index: number) => {
            const unrealizedPnL = pos.unrealized_pl || 0;
            const pnlPercent = (pos.unrealized_plpc || 0) * 100;
            const pnlFormatted = formatProfitLoss(unrealizedPnL);

            return (
              <View key={`${pos.symbol}-${index}`} style={styles.positionCard}>
                <View style={styles.positionHeader}>
                  <Text style={styles.positionSymbol}>{pos.symbol}</Text>
                  <View style={[
                    styles.positionBadge,
                    pos.side === 'long' ? styles.badgeBuy : styles.badgeSell
                  ]}>
                    <Text style={styles.badgeText}>
                      {pos.side === 'long' ? 'BUY' : 'SELL'}
                    </Text>
                  </View>
                </View>
                <View style={styles.positionDetails}>
                  <Text style={styles.positionInfo}>
                    {formatNumber(pos.qty)} shares @ {formatCurrency(pos.avg_entry_price)}
                  </Text>
                  <Text style={styles.positionInfo}>
                    Current: {formatCurrency(pos.current_price)}
                  </Text>
                </View>
                <View style={styles.positionPnL}>
                  <Text style={[
                    styles.pnlValue,
                    pnlFormatted.isProfit ? styles.profit : styles.loss
                  ]}>
                    {pnlFormatted.formatted}
                  </Text>
                  <Text style={[
                    styles.pnlPercent,
                    pnlPercent >= 0 ? styles.profit : styles.loss
                  ]}>
                    ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
                  </Text>
                </View>
              </View>
            );
          })
        )}
      </View>
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
  header: {
    marginBottom: 24,
  },
  greeting: {
    fontSize: 16,
    color: '#888',
  },
  name: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  statsGrid: {
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#333',
  },
  statCardPrimary: {
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
  },
  statLabel: {
    fontSize: 14,
    color: '#888',
    marginBottom: 8,
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  statSubtext: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  profit: {
    color: '#22c55e',
  },
  loss: {
    color: '#ef4444',
  },
  aiControl: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#333',
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  aiIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#333',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  aiIconActive: {
    backgroundColor: '#22c55e',
  },
  aiIconText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  aiInfo: {
    flex: 1,
  },
  aiTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  aiSubtitle: {
    fontSize: 14,
    color: '#888',
    marginTop: 2,
  },
  aiButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  aiButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  aiButtonStart: {
    backgroundColor: '#22c55e',
  },
  aiButtonStop: {
    backgroundColor: '#ef4444',
  },
  aiButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  closeButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    backgroundColor: '#3b82f6',
  },
  closeButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  aiStats: {
    flexDirection: 'row',
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#333',
  },
  aiStatItem: {
    flex: 1,
  },
  aiStatLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 4,
  },
  aiStatValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  positionsSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 12,
  },
  loader: {
    marginVertical: 24,
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
  positionCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#333',
  },
  positionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  positionSymbol: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginRight: 8,
  },
  positionBadge: {
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
  positionDetails: {
    marginBottom: 8,
  },
  positionInfo: {
    fontSize: 14,
    color: '#888',
    marginBottom: 2,
  },
  positionPnL: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pnlValue: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  pnlPercent: {
    fontSize: 14,
  },
});
