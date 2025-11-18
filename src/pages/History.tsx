import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, ArrowLeft, ArrowUpRight, ArrowDownRight, ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { format } from "date-fns";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";

const History = () => {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const navigate = useNavigate();
  
  // Pagination & filter states
  const [txPage, setTxPage] = useState(1);
  const [tradePage, setTradePage] = useState(1);
  const [txSortOrder, setTxSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [tradeSortOrder, setTradeSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [txDateRange, setTxDateRange] = useState<{ from?: Date; to?: Date }>({});
  const [tradeDateRange, setTradeDateRange] = useState<{ from?: Date; to?: Date }>({});
  const itemsPerPage = 15;

  useEffect(() => {
    const loadData = async () => {
      if (!apiClient.isAuthenticated()) {
        navigate("/auth");
        return;
      }

      try {
        // Load transactions
        const txData = await apiClient.getTransactions();
        setTransactions(txData || []);

        // Load trades
        const tradeData = await apiClient.getTrades();
        setTrades(tradeData || []);
      } catch (error) {
        navigate("/auth");
      }
    };

    loadData();
  }, [navigate]);

  const getStatusBadge = (status: string) => {
    const variants: any = {
      completed: "default",
      pending: "secondary",
      failed: "destructive",
      cancelled: "outline",
    };
    return <Badge variant={variants[status] || "default"}>{status}</Badge>;
  };

  // Filter and sort transactions
  const getFilteredTransactions = () => {
    let filtered = [...transactions];
    
    // Date range filter
    if (txDateRange.from || txDateRange.to) {
      filtered = filtered.filter(tx => {
        const txDate = new Date(tx.created_at);
        txDate.setHours(0, 0, 0, 0);
        
        if (txDateRange.from && txDateRange.to) {
          const from = new Date(txDateRange.from);
          from.setHours(0, 0, 0, 0);
          const to = new Date(txDateRange.to);
          to.setHours(23, 59, 59, 999);
          return txDate >= from && txDate <= to;
        } else if (txDateRange.from) {
          const from = new Date(txDateRange.from);
          from.setHours(0, 0, 0, 0);
          return txDate >= from;
        } else if (txDateRange.to) {
          const to = new Date(txDateRange.to);
          to.setHours(23, 59, 59, 999);
          return txDate <= to;
        }
        return true;
      });
    }
    
    // Sort
    filtered.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return txSortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    return filtered;
  };

  // Filter and sort trades
  const getFilteredTrades = () => {
    let filtered = [...trades];
    
    // Date range filter
    if (tradeDateRange.from || tradeDateRange.to) {
      filtered = filtered.filter(trade => {
        const tradeDate = new Date(trade.created_at);
        tradeDate.setHours(0, 0, 0, 0);
        
        if (tradeDateRange.from && tradeDateRange.to) {
          const from = new Date(tradeDateRange.from);
          from.setHours(0, 0, 0, 0);
          const to = new Date(tradeDateRange.to);
          to.setHours(23, 59, 59, 999);
          return tradeDate >= from && tradeDate <= to;
        } else if (tradeDateRange.from) {
          const from = new Date(tradeDateRange.from);
          from.setHours(0, 0, 0, 0);
          return tradeDate >= from;
        } else if (tradeDateRange.to) {
          const to = new Date(tradeDateRange.to);
          to.setHours(23, 59, 59, 999);
          return tradeDate <= to;
        }
        return true;
      });
    }
    
    // Sort
    filtered.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return tradeSortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    return filtered;
  };

  // Paginate data
  const paginateData = (data: any[], page: number) => {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return data.slice(startIndex, endIndex);
  };

  const filteredTransactions = getFilteredTransactions();
  const filteredTrades = getFilteredTrades();
  const paginatedTransactions = paginateData(filteredTransactions, txPage);
  const paginatedTrades = paginateData(filteredTrades, tradePage);
  
  const txTotalPages = Math.ceil(filteredTransactions.length / itemsPerPage);
  const tradeTotalPages = Math.ceil(filteredTrades.length / itemsPerPage);

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

        <h2 className="text-3xl font-bold mb-6">Transaction History</h2>

        <Tabs defaultValue="trades" className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="trades">Trading History</TabsTrigger>
          </TabsList>

          <TabsContent value="transactions">
            <div className="mb-4 flex flex-wrap gap-4 items-center justify-between">
              <div className="flex gap-3 items-center">
                <Select value={txSortOrder} onValueChange={(value: any) => { setTxSortOrder(value); setTxPage(1); }}>
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
                      {txDateRange.from ? (
                        txDateRange.to ? (
                          `${format(txDateRange.from, "MMM dd")} - ${format(txDateRange.to, "MMM dd, yyyy")}`
                        ) : (
                          `From ${format(txDateRange.from, "MMM dd, yyyy")}`
                        )
                      ) : txDateRange.to ? (
                        `Until ${format(txDateRange.to, "MMM dd, yyyy")}`
                      ) : (
                        "Filter by Date Range"
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0">
                    <CalendarComponent
                      mode="range"
                      selected={txDateRange}
                      onSelect={(range: any) => { setTxDateRange(range || {}); setTxPage(1); }}
                      numberOfMonths={2}
                    />
                  </PopoverContent>
                </Popover>

                {(txDateRange.from || txDateRange.to) && (
                  <Button variant="ghost" size="sm" onClick={() => { setTxDateRange({}); setTxPage(1); }}>
                    Clear Date
                  </Button>
                )}
              </div>

              <div className="text-sm text-muted-foreground">
                Showing {filteredTransactions.length === 0 ? 0 : ((txPage - 1) * itemsPerPage) + 1}-{Math.min(txPage * itemsPerPage, filteredTransactions.length)} of {filteredTransactions.length}
              </div>
            </div>

            <Card className="p-6 bg-card border-border">
              {filteredTransactions.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No transactions found</p>
              ) : (
                <div className="space-y-4">
                  {paginatedTransactions.map((tx) => (
                    <Card key={tx.id} className="p-4 bg-secondary border-border">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            tx.type === "deposit" ? "bg-accent/10" : "bg-destructive/10"
                          }`}>
                            {tx.type === "deposit" ? (
                              <ArrowDownRight className="h-5 w-5 text-accent" />
                            ) : (
                              <ArrowUpRight className="h-5 w-5 text-destructive" />
                            )}
                          </div>
                          <div>
                            <div className="font-semibold capitalize">{tx.type}</div>
                            <div className="text-sm text-muted-foreground">
                              {format(new Date(tx.created_at), "MMM dd, yyyy HH:mm")}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-lg">
                            {tx.currency} {parseFloat(tx.amount).toFixed(2)}
                          </div>
                          <div className="mt-1">{getStatusBadge(tx.status)}</div>
                        </div>
                      </div>
                      {tx.payment_method && (
                        <div className="mt-2 text-sm text-muted-foreground">
                          via {tx.payment_method}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              )}
              
              {txTotalPages > 1 && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setTxPage(p => Math.max(1, p - 1))}
                    disabled={txPage === 1}
                    className="gap-1"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  
                  <span className="text-sm text-muted-foreground">
                    Page {txPage} of {txTotalPages}
                  </span>
                  
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setTxPage(p => Math.min(txTotalPages, p + 1))}
                    disabled={txPage === txTotalPages}
                    className="gap-1"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="trades">
            <div className="mb-4 flex flex-wrap gap-4 items-center justify-between">
              <div className="flex gap-3 items-center">
                <Select value={tradeSortOrder} onValueChange={(value: any) => { setTradeSortOrder(value); setTradePage(1); }}>
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
                      {tradeDateRange.from ? (
                        tradeDateRange.to ? (
                          `${format(tradeDateRange.from, "MMM dd")} - ${format(tradeDateRange.to, "MMM dd, yyyy")}`
                        ) : (
                          `From ${format(tradeDateRange.from, "MMM dd, yyyy")}`
                        )
                      ) : tradeDateRange.to ? (
                        `Until ${format(tradeDateRange.to, "MMM dd, yyyy")}`
                      ) : (
                        "Filter by Date Range"
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0">
                    <CalendarComponent
                      mode="range"
                      selected={tradeDateRange}
                      onSelect={(range: any) => { setTradeDateRange(range || {}); setTradePage(1); }}
                      numberOfMonths={2}
                    />
                  </PopoverContent>
                </Popover>

                {(tradeDateRange.from || tradeDateRange.to) && (
                  <Button variant="ghost" size="sm" onClick={() => { setTradeDateRange({}); setTradePage(1); }}>
                    Clear Date
                  </Button>
                )}
              </div>

              <div className="text-sm text-muted-foreground">
                Showing {filteredTrades.length === 0 ? 0 : ((tradePage - 1) * itemsPerPage) + 1}-{Math.min(tradePage * itemsPerPage, filteredTrades.length)} of {filteredTrades.length}
              </div>
            </div>

            <Card className="p-6 bg-card border-border">
              {filteredTrades.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No trades found</p>
              ) : (
                <div className="space-y-4">
                  {paginatedTrades.map((trade) => (
                    <Card key={trade.id} className="p-4 bg-secondary border-border">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold">{trade.symbol}</span>
                            <Badge variant={trade.side === "BUY" ? "default" : "destructive"}>
                              {trade.side}
                            </Badge>
                            {trade.instrument_type === 'option' && (
                              <Badge variant="outline" className="bg-purple-500/10 text-purple-700 border-purple-500/20">
                                {trade.option_type?.toUpperCase()} OPTION
                              </Badge>
                            )}
                            {trade.confidence !== undefined && trade.confidence !== null && (
                              <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                                AI TRADE
                              </Badge>
                            )}
                            {trade.status === "open" && (
                              <Badge variant="secondary">OPEN</Badge>
                            )}
                          </div>
                          <div className="text-sm text-muted-foreground mt-1">
                            {trade.instrument_type === 'option' ? (
                              <div className="space-y-1">
                                <div>Underlying: {trade.underlying_asset}</div>
                                <div>Strike: ${parseFloat(trade.strike_price || 0).toFixed(2)} | Expiry: {trade.expiration_date ? format(new Date(trade.expiration_date), "MMM dd, yyyy") : 'N/A'}</div>
                                <div>{trade.quantity} contracts ({trade.contract_size || 100} shares) @ ${parseFloat(trade.premium || 0).toFixed(2)}</div>
                              </div>
                            ) : (
                              <div>{trade.quantity} shares @ ${parseFloat(trade.entry_price).toFixed(2)}</div>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          {trade.pnl && (
                            <div className={`font-bold flex items-center gap-1 ${
                              parseFloat(trade.pnl) >= 0 ? "text-accent" : "text-destructive"
                            }`}>
                              {parseFloat(trade.pnl) >= 0 ? (
                                <ArrowUpRight className="h-4 w-4" />
                              ) : (
                                <ArrowDownRight className="h-4 w-4" />
                              )}
                              ${Math.abs(parseFloat(trade.pnl)).toFixed(2)}
                            </div>
                          )}
                          <div className="text-sm text-muted-foreground">
                            {format(new Date(trade.created_at), "MMM dd HH:mm")}
                          </div>
                        </div>
                      </div>
                      {trade.confidence && (
                        <div className="text-xs text-muted-foreground">
                          AI Confidence: {trade.confidence}%
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              )}
              
              {tradeTotalPages > 1 && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setTradePage(p => Math.max(1, p - 1))}
                    disabled={tradePage === 1}
                    className="gap-1"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  
                  <span className="text-sm text-muted-foreground">
                    Page {tradePage} of {tradeTotalPages}
                  </span>
                  
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setTradePage(p => Math.min(tradeTotalPages, p + 1))}
                    disabled={tradePage === tradeTotalPages}
                    className="gap-1"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default History;
