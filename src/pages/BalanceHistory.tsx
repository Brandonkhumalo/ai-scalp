import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, ArrowLeft, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { format } from "date-fns";
import { formatCurrency, formatProfitLoss, formatNumber } from "@/lib/formatters";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";

const BalanceHistory = () => {
  const [historyData, setHistoryData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  
  // Pagination & filter states
  const [currentPage, setCurrentPage] = useState(1);
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date }>({});
  const itemsPerPage = 15;

  useEffect(() => {
    const loadBalanceHistory = async () => {
      if (!apiClient.isAuthenticated()) {
        navigate("/auth");
        return;
      }

      try {
        const data = await apiClient.getBalanceHistory();
        setHistoryData(data);
      } catch (error) {
        console.error('Error loading balance history:', error);
        navigate("/auth");
      } finally {
        setLoading(false);
      }
    };

    loadBalanceHistory();
  }, [navigate]);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'deposit':
        return <ArrowUpRight className="h-5 w-5 text-green-500" />;
      case 'withdraw':
        return <ArrowDownRight className="h-5 w-5 text-red-500" />;
      case 'trade':
        return <Activity className="h-5 w-5 text-blue-500" />;
      default:
        return <Activity className="h-5 w-5 text-muted-foreground" />;
    }
  };

  const getTypeBadge = (type: string, balanceChange: number) => {
    if (type === 'trade') {
      return balanceChange > 0 ? (
        <Badge variant="default" className="bg-green-600">Profit</Badge>
      ) : (
        <Badge variant="destructive">Loss</Badge>
      );
    }
    
    return (
      <Badge variant={type === 'deposit' ? 'default' : 'secondary'}>
        {type.charAt(0).toUpperCase() + type.slice(1)}
      </Badge>
    );
  };

  // Filter and sort balance history
  const getFilteredHistory = () => {
    if (!historyData?.history) return [];
    
    let filtered = [...historyData.history];
    
    // Date range filter
    if (dateRange.from || dateRange.to) {
      filtered = filtered.filter((item: any) => {
        const itemDate = new Date(item.timestamp);
        itemDate.setHours(0, 0, 0, 0);
        
        if (dateRange.from && dateRange.to) {
          const from = new Date(dateRange.from);
          from.setHours(0, 0, 0, 0);
          const to = new Date(dateRange.to);
          to.setHours(23, 59, 59, 999);
          return itemDate >= from && itemDate <= to;
        } else if (dateRange.from) {
          const from = new Date(dateRange.from);
          from.setHours(0, 0, 0, 0);
          return itemDate >= from;
        } else if (dateRange.to) {
          const to = new Date(dateRange.to);
          to.setHours(23, 59, 59, 999);
          return itemDate <= to;
        }
        return true;
      });
    }
    
    // Sort
    filtered.sort((a: any, b: any) => {
      const dateA = new Date(a.timestamp).getTime();
      const dateB = new Date(b.timestamp).getTime();
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    return filtered;
  };

  // Paginate data
  const paginateData = (data: any[], page: number) => {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return data.slice(startIndex, endIndex);
  };

  const filteredHistory = getFilteredHistory();
  const paginatedHistory = paginateData(filteredHistory, currentPage);
  const totalPages = Math.ceil(filteredHistory.length / itemsPerPage);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading balance history...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <Link to="/dashboard" className="flex items-center gap-2">
            <Activity className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold gradient-primary bg-clip-text text-transparent">ZimAI Trader</h1>
          </Link>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <Link to="/dashboard" className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6 transition-smooth">
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>

        <div className="mb-8">
          <h2 className="text-3xl font-bold mb-2">Balance History</h2>
          <p className="text-muted-foreground">Complete audit trail of your account balance</p>
        </div>

        <Card className="p-6 bg-card border-border mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground mb-1">Current Balance</p>
              <p className="text-3xl font-bold">{formatCurrency(historyData?.current_balance)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground mb-1">Total Entries</p>
              <p className="text-2xl font-semibold">{formatNumber(historyData?.history?.length || 0)}</p>
            </div>
          </div>
        </Card>

        <div className="mb-4 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex gap-3 items-center">
            <Select value={sortOrder} onValueChange={(value: any) => { setSortOrder(value); setCurrentPage(1); }}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Newest First</SelectItem>
                <SelectItem value="oldest">Oldest First</SelectItem>
              </SelectContent>
            </Select>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <Calendar className="h-4 w-4" />
                  {dateRange.from ? (
                    dateRange.to ? (
                      `${format(dateRange.from, "MMM dd")} - ${format(dateRange.to, "MMM dd, yyyy")}`
                    ) : (
                      `From ${format(dateRange.from, "MMM dd, yyyy")}`
                    )
                  ) : dateRange.to ? (
                    `Until ${format(dateRange.to, "MMM dd, yyyy")}`
                  ) : (
                    "Filter by Date Range"
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0">
                <CalendarComponent
                  mode="range"
                  selected={dateRange}
                  onSelect={(range: any) => { setDateRange(range || {}); setCurrentPage(1); }}
                  numberOfMonths={2}
                />
              </PopoverContent>
            </Popover>

            {(dateRange.from || dateRange.to) && (
              <Button variant="ghost" size="sm" onClick={() => { setDateRange({}); setCurrentPage(1); }}>
                Clear Date
              </Button>
            )}
          </div>

          <div className="text-sm text-muted-foreground">
            Showing {filteredHistory.length === 0 ? 0 : ((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, filteredHistory.length)} of {filteredHistory.length}
          </div>
        </div>

        <Card className="p-6 bg-card border-border">
          {filteredHistory.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No balance history found</p>
          ) : (
            <div className="space-y-3">
              {paginatedHistory.map((item: any) => (
                <Card key={item.id} className="p-4 bg-secondary border-border hover:border-primary/50 transition-smooth">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1">
                      <div className="mt-1">
                        {getTypeIcon(item.type)}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium">{item.description}</p>
                          {getTypeBadge(item.type, item.balance_change)}
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-2">
                          {format(new Date(item.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                        </p>

                        {item.trade_details && (
                          <div className="text-sm text-muted-foreground space-y-1 mt-2 p-2 bg-background/50 rounded">
                            <p><span className="font-medium">Symbol:</span> {item.trade_details.symbol}</p>
                            <p><span className="font-medium">Type:</span> <Badge variant={item.trade_details.side === 'BUY' ? 'default' : 'destructive'} className="text-xs">{item.trade_details.side}</Badge></p>
                            <p><span className="font-medium">Quantity:</span> {formatNumber(item.trade_details.quantity)}</p>
                            <p><span className="font-medium">Entry:</span> {formatCurrency(item.trade_details.entry_price)}</p>
                            {item.trade_details.exit_price && (
                              <p><span className="font-medium">Exit:</span> {formatCurrency(item.trade_details.exit_price)}</p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="text-right min-w-[140px]">
                      <div className="flex items-center justify-end gap-1 mb-1">
                        {item.balance_change > 0 ? (
                          <TrendingUp className="h-4 w-4 text-accent" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-destructive" />
                        )}
                        <p className={`font-semibold ${formatProfitLoss(item.balance_change).colorClass}`}>
                          {formatProfitLoss(item.balance_change).formatted}
                        </p>
                      </div>
                      
                      <div className="text-sm space-y-0.5">
                        <p className="text-muted-foreground">
                          Before: {formatCurrency(item.balance_before)}
                        </p>
                        <p className="font-medium">
                          After: {formatCurrency(item.balance_after)}
                        </p>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
          
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="gap-1"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              
              <span className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="gap-1"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default BalanceHistory;
