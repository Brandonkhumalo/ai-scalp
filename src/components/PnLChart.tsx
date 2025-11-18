import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency } from "@/lib/formatters";
import { TrendingUp, TrendingDown } from "lucide-react";

interface PnLDataPoint {
  date: string;
  cumulativePnL: number;
  dailyPnL: number;
  timestamp: number;
}

export const PnLChart = () => {
  const [chartData, setChartData] = useState<PnLDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPnL, setTotalPnL] = useState(0);

  useEffect(() => {
    const loadPnLData = async () => {
      try {
        // Fetch Alpaca equity history
        const response = await apiClient.get('/alpaca-equity-history/');
        
        if (!response.history || response.history.length === 0) {
          setLoading(false);
          return;
        }

        // Convert Alpaca snapshots to chart data points
        const startingEquity = 100000; // Assumed starting balance
        const dataPoints: PnLDataPoint[] = [];
        
        // Group by date and take the latest snapshot per day
        const snapshotsByDate: { [key: string]: any } = {};
        
        response.history.forEach((snapshot: any) => {
          const date = new Date(snapshot.timestamp);
          const dateKey = date.toISOString().split('T')[0];
          
          // Keep the latest snapshot for each day
          if (!snapshotsByDate[dateKey] || new Date(snapshot.timestamp) > new Date(snapshotsByDate[dateKey].timestamp)) {
            snapshotsByDate[dateKey] = snapshot;
          }
        });
        
        // Convert to sorted array using pre-calculated daily P&L from Alpaca
        const sortedDates = Object.entries(snapshotsByDate).sort(([dateA], [dateB]) => dateA.localeCompare(dateB));
        
        sortedDates.forEach(([date, snapshot]: [string, any]) => {
          const equity = snapshot.equity;
          const cumulativePnL = equity - startingEquity;
          
          // Use Alpaca's pre-calculated daily P&L (equity - last_equity from yesterday)
          // This ensures consistency with dashboard values
          const dailyPnL = snapshot.daily_pl || 0;
          
          dataPoints.push({
            date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
            cumulativePnL,
            dailyPnL,
            timestamp: new Date(date).getTime()
          });
        });

        setChartData(dataPoints);
        setTotalPnL(dataPoints.length > 0 ? dataPoints[dataPoints.length - 1].cumulativePnL : 0);
        setLoading(false);
      } catch (error) {
        console.error('Error loading Alpaca P&L data:', error);
        setLoading(false);
      }
    };

    loadPnLData();
    
    // Refresh every 10 seconds
    const interval = setInterval(loadPnLData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Profit & Loss Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            Loading chart data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (chartData.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Profit & Loss Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            No trading data available yet
          </div>
        </CardContent>
      </Card>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-card border border-border p-3 rounded-lg shadow-lg">
          <p className="text-sm font-semibold mb-1">{data.date}</p>
          <p className="text-sm">
            Daily P&L: <span className={data.dailyPnL >= 0 ? "text-accent" : "text-destructive"}>
              {formatCurrency(data.dailyPnL)}
            </span>
          </p>
          <p className="text-sm font-bold">
            Cumulative: <span className={data.cumulativePnL >= 0 ? "text-accent" : "text-destructive"}>
              {formatCurrency(data.cumulativePnL)}
            </span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Profit & Loss Chart</CardTitle>
          <div className="flex items-center gap-2">
            {totalPnL >= 0 ? (
              <TrendingUp className="h-5 w-5 text-accent" />
            ) : (
              <TrendingDown className="h-5 w-5 text-destructive" />
            )}
            <span className={`text-lg font-bold ${totalPnL >= 0 ? 'text-accent' : 'text-destructive'}`}>
              {formatCurrency(totalPnL)}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
            <XAxis 
              dataKey="date" 
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
            />
            <YAxis 
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
              tickFormatter={(value) => `$${value.toFixed(0)}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />
            <Line
              type="monotone"
              dataKey="cumulativePnL"
              name="Cumulative P&L"
              stroke={totalPnL >= 0 ? "#10b981" : "#ef4444"}
              strokeWidth={3}
              dot={{ fill: totalPnL >= 0 ? "#10b981" : "#ef4444", r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
