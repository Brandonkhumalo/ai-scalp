import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { LowBalanceDialog } from "@/components/LowBalanceDialog";

export const OptionsTradeForm = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [showLowBalanceDialog, setShowLowBalanceDialog] = useState(false);
  const [userBalance, setUserBalance] = useState(0);
  const [formData, setFormData] = useState({
    underlying_asset: "",
    option_type: "call" as "call" | "put",
    strike_price: "",
    expiration_date: "",
    quantity: "",
    premium: "",
    side: "buy" as "buy" | "sell",
  });

  useEffect(() => {
    const fetchBalance = async () => {
      try {
        const profile = await apiClient.getProfile();
        setUserBalance(parseFloat(profile?.usd_balance || 0));
      } catch (error) {
        console.error("Error fetching balance:", error);
      }
    };
    
    if (apiClient.isAuthenticated()) {
      fetchBalance();
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiClient.isAuthenticated()) {
      toast({
        title: "Error",
        description: "You must be logged in to trade options",
        variant: "destructive",
      });
      return;
    }
    
    const profile = await apiClient.getProfile();
    const currentBalance = parseFloat(profile?.usd_balance || 0);
    setUserBalance(currentBalance);
    
    if (currentBalance < 5) {
      setShowLowBalanceDialog(true);
      return;
    }
    
    setLoading(true);

    try {

      await apiClient.createTrade({
        instrument_type: "option",
        symbol: `${formData.underlying_asset} ${formData.strike_price}${formData.option_type[0].toUpperCase()}`,
        underlying_asset: formData.underlying_asset,
        option_type: formData.option_type,
        strike_price: parseFloat(formData.strike_price),
        expiration_date: formData.expiration_date,
        quantity: parseInt(formData.quantity),
        premium: parseFloat(formData.premium),
        entry_price: parseFloat(formData.premium),
        side: formData.side,
        status: "open",
      });

      toast({
        title: "Success",
        description: "Options trade created successfully",
      });

      setFormData({
        underlying_asset: "",
        option_type: "call",
        strike_price: "",
        expiration_date: "",
        quantity: "",
        premium: "",
        side: "buy",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade Options</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="underlying">Underlying Asset</Label>
              <Input
                id="underlying"
                placeholder="e.g., AAPL"
                value={formData.underlying_asset}
                onChange={(e) => setFormData({ ...formData, underlying_asset: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="option-type">Option Type</Label>
              <Select
                value={formData.option_type}
                onValueChange={(value: "call" | "put") => setFormData({ ...formData, option_type: value })}
              >
                <SelectTrigger id="option-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="call">Call</SelectItem>
                  <SelectItem value="put">Put</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="strike">Strike Price ($)</Label>
              <Input
                id="strike"
                type="number"
                step="0.01"
                placeholder="150.00"
                value={formData.strike_price}
                onChange={(e) => setFormData({ ...formData, strike_price: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expiration">Expiration Date</Label>
              <Input
                id="expiration"
                type="date"
                value={formData.expiration_date}
                onChange={(e) => setFormData({ ...formData, expiration_date: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="contracts">Contracts</Label>
              <Input
                id="contracts"
                type="number"
                placeholder="1"
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="premium">Premium ($)</Label>
              <Input
                id="premium"
                type="number"
                step="0.01"
                placeholder="2.50"
                value={formData.premium}
                onChange={(e) => setFormData({ ...formData, premium: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="side">Side</Label>
            <Select
              value={formData.side}
              onValueChange={(value: "buy" | "sell") => setFormData({ ...formData, side: value })}
            >
              <SelectTrigger id="side">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="buy">Buy to Open</SelectItem>
                <SelectItem value="sell">Sell to Open</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Processing..." : "Execute Options Trade"}
          </Button>
        </form>
      </CardContent>
      
      <LowBalanceDialog
        open={showLowBalanceDialog}
        onOpenChange={setShowLowBalanceDialog}
        currentBalance={userBalance}
      />
    </Card>
  );
};
