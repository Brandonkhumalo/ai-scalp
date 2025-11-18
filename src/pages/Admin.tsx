import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useHasRole } from "@/hooks/useUserRole";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { 
  Shield, ArrowLeft, CheckCircle, XCircle, Users, TrendingUp, 
  DollarSign, Activity, Clock, RefreshCw 
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppNavbar } from "@/components/AppNavbar";

interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  usd_balance: number;
  zwl_balance: number;
  approval_status: 'pending' | 'approved' | 'rejected';
  ai_trading_enabled: boolean;
  is_currently_trading: boolean;
  open_trades_count: number;
  total_pnl: number;
  created_at: string;
  approved_at: string | null;
  approved_by_email: string | null;
}

interface ActiveTrader {
  user_id: number;
  email: string;
  full_name: string;
  usd_balance: number;
  open_trades: Array<{
    symbol: string;
    side: string;
    quantity: number;
    entry_price: number;
    ai_confidence: number;
    created_at: string;
  }>;
  pnl_today: number;
  pnl_all_time: number;
  ai_trading_enabled: boolean;
}

interface PlatformOverview {
  total_users: number;
  pending_approvals: number;
  approved_users: number;
  rejected_users: number;
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  total_platform_pnl: number;
  ai_enabled_users: number;
}

export default function Admin() {
  const navigate = useNavigate();
  const { hasRole, isLoading } = useHasRole('admin');
  const { toast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [activeTraders, setActiveTraders] = useState<ActiveTrader[]>([]);
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!isLoading && !hasRole) {
      navigate('/dashboard');
      return;
    }

    if (hasRole) {
      loadAdminData();
    }
  }, [hasRole, isLoading, navigate]);

  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      loadTradingStats();
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const loadAdminData = async () => {
    setLoading(true);
    await Promise.all([
      loadUsers(),
      loadTradingStats(),
      loadOverview()
    ]);
    setLoading(false);
  };

  const loadUsers = async () => {
    try {
      const response = await fetch('/api/admin/users/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      if (data.success) {
        setUsers(data.users);
      }
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const loadTradingStats = async () => {
    try {
      const response = await fetch('/api/admin/trading-stats/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      if (data.success) {
        setActiveTraders(data.active_traders);
      }
    } catch (error) {
      console.error('Error loading trading stats:', error);
    }
  };

  const loadOverview = async () => {
    try {
      const response = await fetch('/api/admin/platform-overview/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      if (data.success) {
        setOverview(data.overview);
      }
    } catch (error) {
      console.error('Error loading overview:', error);
    }
  };

  const approveUser = async (userId: number) => {
    try {
      const response = await fetch(`/api/admin/users/${userId}/approve/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: "Success",
          description: data.message,
        });
        loadUsers();
        loadOverview();
      } else {
        throw new Error(data.error);
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to approve user",
        variant: "destructive",
      });
    }
  };

  const rejectUser = async (userId: number) => {
    try {
      const response = await fetch(`/api/admin/users/${userId}/reject/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: "Success",
          description: data.message,
        });
        loadUsers();
        loadOverview();
      } else {
        throw new Error(data.error);
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to reject user",
        variant: "destructive",
      });
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (isLoading || loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!hasRole) {
    return null;
  }

  const pendingUsers = users.filter(u => u.approval_status === 'pending');
  const approvedUsers = users.filter(u => u.approval_status === 'approved');
  const rejectedUsers = users.filter(u => u.approval_status === 'rejected');

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <div className="p-4">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => navigate('/dashboard')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Shield className="h-8 w-8" />
              <div>
                <h1 className="text-3xl font-bold">Admin Dashboard</h1>
                <p className="text-muted-foreground">User management & real-time trading monitor</p>
              </div>
            </div>
            <Button 
              variant={autoRefresh ? "default" : "outline"}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
              {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
            </Button>
          </div>

        {overview && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-muted-foreground" />
                  <span className="text-2xl font-bold">{overview.total_users}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {overview.pending_approvals} pending approval
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Active Trades</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-muted-foreground" />
                  <span className="text-2xl font-bold">{overview.open_trades}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {overview.total_trades} total trades
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Platform P&L</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <TrendingUp className={`h-5 w-5 ${overview.total_platform_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`} />
                  <span className={`text-2xl font-bold ${overview.total_platform_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatCurrency(overview.total_platform_pnl)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  All-time platform profit/loss
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">AI Trading</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-muted-foreground" />
                  <span className="text-2xl font-bold">{overview.ai_enabled_users}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Users with AI enabled
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs defaultValue="pending" className="space-y-4">
          <TabsList>
            <TabsTrigger value="pending">
              Pending Approval ({pendingUsers.length})
            </TabsTrigger>
            <TabsTrigger value="approved">
              Approved ({approvedUsers.length})
            </TabsTrigger>
            <TabsTrigger value="rejected">
              Rejected ({rejectedUsers.length})
            </TabsTrigger>
            <TabsTrigger value="trading">
              Live Trading ({activeTraders.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pending" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending User Approvals</CardTitle>
                <CardDescription>Review and approve new user registrations</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {pendingUsers.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No pending approvals</p>
                ) : (
                  pendingUsers.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <p className="font-medium">{user.email}</p>
                        <p className="text-sm text-muted-foreground">{user.full_name || 'No name provided'}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Registered: {formatDate(user.created_at)}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => approveUser(user.id)}
                          className="bg-green-600 hover:bg-green-700"
                        >
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => rejectUser(user.id)}
                        >
                          <XCircle className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="approved" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Approved Users</CardTitle>
                <CardDescription>Users authorized to trade on the platform</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {approvedUsers.map((user) => (
                  <div key={user.id} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{user.email}</p>
                          {user.is_currently_trading && (
                            <Badge variant="default" className="bg-green-600">
                              <Activity className="h-3 w-3 mr-1" />
                              Trading
                            </Badge>
                          )}
                          {user.ai_trading_enabled && (
                            <Badge variant="secondary">AI Enabled</Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-3 gap-4 mt-2 text-sm">
                          <div>
                            <p className="text-muted-foreground">Balance</p>
                            <p className="font-medium">{formatCurrency(user.usd_balance)}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Open Trades</p>
                            <p className="font-medium">{user.open_trades_count}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Total P&L</p>
                            <p className={`font-medium ${user.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatCurrency(user.total_pnl)}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rejected" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Rejected Users</CardTitle>
                <CardDescription>Users who have been denied access</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {rejectedUsers.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No rejected users</p>
                ) : (
                  rejectedUsers.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-4 border rounded-lg opacity-60">
                      <div>
                        <p className="font-medium">{user.email}</p>
                        <p className="text-sm text-muted-foreground">
                          Rejected: {user.approved_at ? formatDate(user.approved_at) : 'N/A'}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="trading" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-green-600 animate-pulse" />
                  Real-Time Trading Monitor
                </CardTitle>
                <CardDescription>
                  Active traders and their current positions (auto-refreshes every 5s)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {activeTraders.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No active traders</p>
                ) : (
                  activeTraders.map((trader) => (
                    <div key={trader.user_id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{trader.email}</p>
                            <Badge variant="default" className="bg-green-600">
                              <Clock className="h-3 w-3 mr-1 animate-pulse" />
                              Live
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">{trader.full_name}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm text-muted-foreground">Balance</p>
                          <p className="font-bold">{formatCurrency(trader.usd_balance)}</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 p-3 bg-muted/50 rounded">
                        <div>
                          <p className="text-xs text-muted-foreground">Today's P&L</p>
                          <p className={`font-bold ${trader.pnl_today >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatCurrency(trader.pnl_today)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">All-Time P&L</p>
                          <p className={`font-bold ${trader.pnl_all_time >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatCurrency(trader.pnl_all_time)}
                          </p>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Open Positions ({trader.open_trades.length})</p>
                        {trader.open_trades.map((trade, idx) => (
                          <div key={idx} className="flex items-center justify-between text-sm p-2 bg-background rounded">
                            <div className="flex items-center gap-2">
                              <Badge variant={trade.side === 'buy' ? 'default' : 'secondary'}>
                                {trade.side.toUpperCase()}
                              </Badge>
                              <span className="font-medium">{trade.symbol}</span>
                              <span className="text-muted-foreground">
                                {trade.quantity} @ {formatCurrency(trade.entry_price)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                AI: {trade.ai_confidence}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        </div>
      </div>
    </div>
  );
}
