import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { apiClient } from '../services/api';
import { formatCurrency, formatShortDate } from '../utils/formatters';

interface EquityPoint {
  timestamp: string;
  equity: number;
  profit_loss: number;
  profit_loss_pct: number;
}

export function BalanceHistoryScreen() {
  const [equityHistory, setEquityHistory] = useState<EquityPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const data = await apiClient.getAlpacaEquityHistory();
      setEquityHistory(data.history || []);
    } catch (error) {
      console.error('Error loading equity history:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const latestEquity = equityHistory.length > 0 ? equityHistory[equityHistory.length - 1] : null;
  const firstEquity = equityHistory.length > 0 ? equityHistory[0] : null;
  const totalChange = latestEquity && firstEquity 
    ? latestEquity.equity - firstEquity.equity 
    : 0;
  const totalChangePercent = firstEquity && firstEquity.equity > 0
    ? ((totalChange / firstEquity.equity) * 100)
    : 0;

  const maxEquity = Math.max(...equityHistory.map(p => p.equity), 0);
  const minEquity = Math.min(...equityHistory.map(p => p.equity), maxEquity);
  const range = maxEquity - minEquity || 1;

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
      <Text style={styles.title}>Balance History</Text>

      <View style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Current Equity</Text>
            <Text style={styles.summaryValue}>
              {formatCurrency(latestEquity?.equity || 0)}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Total Change</Text>
            <Text style={[
              styles.summaryValue,
              totalChange >= 0 ? styles.profit : styles.loss
            ]}>
              {totalChange >= 0 ? '+' : ''}{formatCurrency(totalChange)}
            </Text>
            <Text style={[
              styles.summaryPercent,
              totalChangePercent >= 0 ? styles.profit : styles.loss
            ]}>
              ({totalChangePercent >= 0 ? '+' : ''}{totalChangePercent.toFixed(2)}%)
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.chartContainer}>
        <Text style={styles.chartTitle}>Equity Over Time</Text>
        {equityHistory.length > 0 ? (
          <View style={styles.chart}>
            <View style={styles.chartYAxis}>
              <Text style={styles.axisLabel}>{formatCurrency(maxEquity)}</Text>
              <Text style={styles.axisLabel}>{formatCurrency(minEquity)}</Text>
            </View>
            <View style={styles.chartBars}>
              {equityHistory.slice(-20).map((point, index) => {
                const height = ((point.equity - minEquity) / range) * 100;
                return (
                  <View key={index} style={styles.barContainer}>
                    <View
                      style={[
                        styles.bar,
                        {
                          height: `${Math.max(height, 5)}%`,
                          backgroundColor: point.profit_loss >= 0 ? '#22c55e' : '#ef4444',
                        },
                      ]}
                    />
                  </View>
                );
              })}
            </View>
          </View>
        ) : (
          <View style={styles.emptyChart}>
            <Text style={styles.emptyText}>No equity data available</Text>
          </View>
        )}
      </View>

      <Text style={styles.sectionTitle}>Daily History</Text>
      {equityHistory.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No history data available</Text>
        </View>
      ) : (
        [...equityHistory].reverse().slice(0, 30).map((point, index) => (
          <View key={index} style={styles.historyCard}>
            <View style={styles.historyHeader}>
              <Text style={styles.historyDate}>
                {formatShortDate(point.timestamp)}
              </Text>
              <Text style={styles.historyEquity}>
                {formatCurrency(point.equity)}
              </Text>
            </View>
            <View style={styles.historyDetails}>
              <Text style={[
                styles.historyPnL,
                point.profit_loss >= 0 ? styles.profit : styles.loss
              ]}>
                {point.profit_loss >= 0 ? '+' : ''}{formatCurrency(point.profit_loss)}
              </Text>
              <Text style={[
                styles.historyPercent,
                point.profit_loss_pct >= 0 ? styles.profit : styles.loss
              ]}>
                ({point.profit_loss_pct >= 0 ? '+' : ''}{point.profit_loss_pct.toFixed(2)}%)
              </Text>
            </View>
          </View>
        ))
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
    paddingBottom: 32,
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
  summaryCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#333',
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  summaryItem: {
    flex: 1,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  summaryPercent: {
    fontSize: 14,
    marginTop: 2,
  },
  profit: {
    color: '#22c55e',
  },
  loss: {
    color: '#ef4444',
  },
  chartContainer: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#333',
  },
  chartTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 16,
  },
  chart: {
    flexDirection: 'row',
    height: 150,
  },
  chartYAxis: {
    width: 60,
    justifyContent: 'space-between',
    paddingRight: 8,
  },
  axisLabel: {
    fontSize: 10,
    color: '#888',
  },
  chartBars: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 2,
  },
  barContainer: {
    flex: 1,
    height: '100%',
    justifyContent: 'flex-end',
  },
  bar: {
    width: '100%',
    borderRadius: 2,
    minHeight: 4,
  },
  emptyChart: {
    height: 150,
    justifyContent: 'center',
    alignItems: 'center',
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
  historyCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#333',
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  historyDate: {
    fontSize: 14,
    color: '#888',
  },
  historyEquity: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  historyDetails: {
    flexDirection: 'row',
    gap: 8,
  },
  historyPnL: {
    fontSize: 14,
    fontWeight: '600',
  },
  historyPercent: {
    fontSize: 14,
  },
});
