import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  Shield, 
  TrendingUp, 
  Target,
  AlertTriangle,
  Info
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatPercentage } from "@/lib/formatters";

interface AdvancedOrderTypesProps {
  symbol?: string;
  currentPrice?: number;
  onOrderPlaced?: () => void;
}

export const AdvancedOrderTypes = ({ symbol = "AAPL", currentPrice = 0, onOrderPlaced }: AdvancedOrderTypesProps) => {
  const { toast } = useToast();
  const [orderType, setOrderType] = useState<"market" | "limit" | "stop_loss" | "take_profit" | "trailing_stop">("market");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState<string>("100");
  const [limitPrice, setLimitPrice] = useState<string>(currentPrice.toString());
  const [stopLossPrice, setStopLossPrice] = useState<string>("");
  const [takeProfitPrice, setTakeProfitPrice] = useState<string>("");
  const [trailingPercent, setTrailingPercent] = useState<string>("5");
  const [enableStopLoss, setEnableStopLoss] = useState(false);
  const [enableTakeProfit, setEnableTakeProfit] = useState(false);
  const [loading, setLoading] = useState(false);

  const calculateStopLoss = () => {
    if (currentPrice > 0) {
      const slPrice = side === "buy" 
        ? currentPrice * 0.95 // 5% below for buy
        : currentPrice * 1.05; // 5% above for sell
      setStopLossPrice(slPrice.toFixed(2));
    }
  };

  const calculateTakeProfit = () => {
    if (currentPrice > 0) {
      const tpPrice = side === "buy"
        ? currentPrice * 1.10 // 10% above for buy
        : currentPrice * 0.90; // 10% below for sell
      setTakeProfitPrice(tpPrice.toFixed(2));
    }
  };

  const handlePlaceOrder = async () => {
    try {
      setLoading(true);

      const orderData: any = {
        symbol,
        side,
        quantity: parseInt(quantity),
        instrument_type: symbol.includes('/') ? 'forex' : 'stock',
        order_type: orderType
      };

      if (orderType === "limit" || orderType === "stop_loss" || orderType === "take_profit") {
        orderData.limit_price = parseFloat(limitPrice);
      }

      if (orderType === "trailing_stop") {
        orderData.trailing_percent = parseFloat(trailingPercent);
      }

      if (enableStopLoss && stopLossPrice) {
        orderData.stop_loss = parseFloat(stopLossPrice);
      }

      if (enableTakeProfit && takeProfitPrice) {
        orderData.take_profit = parseFloat(takeProfitPrice);
      }

      await apiClient.createTrade(orderData);

      toast({
        title: "Order Placed Successfully",
        description: `${orderType.toUpperCase()} order for ${quantity} ${symbol} at ${limitPrice}`,
      });

      onOrderPlaced?.();
      
      // Reset form
      setQuantity("100");
      setStopLossPrice("");
      setTakeProfitPrice("");
      setEnableStopLoss(false);
      setEnableTakeProfit(false);
    } catch (error: any) {
      toast({
        title: "Order Failed",
        description: error.message || "Failed to place order",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const estimatedCost = parseFloat(quantity || "0") * parseFloat(limitPrice || "0");
  const potentialLoss = enableStopLoss && stopLossPrice 
    ? Math.abs(parseFloat(quantity || "0") * (parseFloat(limitPrice || "0") - parseFloat(stopLossPrice)))
    : 0;
  const potentialProfit = enableTakeProfit && takeProfitPrice
    ? Math.abs(parseFloat(quantity || "0") * (parseFloat(takeProfitPrice) - parseFloat(limitPrice || "0")))
    : 0;
  const riskRewardRatio = potentialLoss > 0 ? (potentialProfit / potentialLoss).toFixed(2) : "N/A";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5" />
          Advanced Order Types
        </CardTitle>
        <CardDescription>
          Use stop loss, take profit, and trailing stops for risk management
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Order Type Selection */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Order Type</Label>
            <Select value={orderType} onValueChange={(v: any) => setOrderType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="market">Market Order</SelectItem>
                <SelectItem value="limit">Limit Order</SelectItem>
                <SelectItem value="stop_loss">Stop Loss Order</SelectItem>
                <SelectItem value="take_profit">Take Profit Order</SelectItem>
                <SelectItem value="trailing_stop">Trailing Stop</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Side</Label>
            <Select value={side} onValueChange={(v: any) => setSide(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="buy">Buy</SelectItem>
                <SelectItem value="sell">Sell</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Symbol and Quantity */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Symbol</Label>
            <Input value={symbol} disabled className="bg-secondary" />
          </div>

          <div className="space-y-2">
            <Label>Quantity</Label>
            <Input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="100"
            />
          </div>
        </div>

        {/* Price Inputs */}
        {orderType !== "market" && orderType !== "trailing_stop" && (
          <div className="space-y-2">
            <Label>
              {orderType === "limit" ? "Limit Price" : 
               orderType === "stop_loss" ? "Stop Loss Price" : 
               "Take Profit Price"}
            </Label>
            <Input
              type="number"
              step="0.01"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              placeholder={currentPrice.toString()}
            />
            <p className="text-xs text-muted-foreground">
              Current market price: {formatCurrency(currentPrice)}
            </p>
          </div>
        )}

        {orderType === "trailing_stop" && (
          <div className="space-y-2">
            <Label>Trailing Percent</Label>
            <Input
              type="number"
              step="0.1"
              value={trailingPercent}
              onChange={(e) => setTrailingPercent(e.target.value)}
              placeholder="5"
            />
            <p className="text-xs text-muted-foreground">
              Order will trail the market by {trailingPercent}%
            </p>
          </div>
        )}

        {/* Stop Loss */}
        <div className="space-y-3 p-4 bg-destructive/10 rounded-lg border border-destructive/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-destructive" />
              <Label htmlFor="stop-loss">Stop Loss</Label>
            </div>
            <Switch
              id="stop-loss"
              checked={enableStopLoss}
              onCheckedChange={setEnableStopLoss}
            />
          </div>
          
          {enableStopLoss && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  type="number"
                  step="0.01"
                  value={stopLossPrice}
                  onChange={(e) => setStopLossPrice(e.target.value)}
                  placeholder="Stop loss price"
                />
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={calculateStopLoss}
                >
                  Auto 5%
                </Button>
              </div>
              {stopLossPrice && (
                <p className="text-xs text-destructive flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Max loss: {formatCurrency(potentialLoss)}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Take Profit */}
        <div className="space-y-3 p-4 bg-accent/10 rounded-lg border border-accent/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-accent" />
              <Label htmlFor="take-profit">Take Profit</Label>
            </div>
            <Switch
              id="take-profit"
              checked={enableTakeProfit}
              onCheckedChange={setEnableTakeProfit}
            />
          </div>
          
          {enableTakeProfit && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  type="number"
                  step="0.01"
                  value={takeProfitPrice}
                  onChange={(e) => setTakeProfitPrice(e.target.value)}
                  placeholder="Take profit price"
                />
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={calculateTakeProfit}
                >
                  Auto 10%
                </Button>
              </div>
              {takeProfitPrice && (
                <p className="text-xs text-accent flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  Target profit: {formatCurrency(potentialProfit)}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Risk/Reward Summary */}
        {(enableStopLoss || enableTakeProfit) && (
          <div className="p-4 bg-secondary rounded-lg space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Info className="h-4 w-4" />
              Risk/Reward Analysis
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Estimated Cost</div>
                <div className="font-bold">{formatCurrency(estimatedCost)}</div>
              </div>
              {enableStopLoss && (
                <div>
                  <div className="text-muted-foreground">Max Risk</div>
                  <div className="font-bold text-destructive">{formatCurrency(potentialLoss)}</div>
                </div>
              )}
              {enableTakeProfit && (
                <div>
                  <div className="text-muted-foreground">Target Profit</div>
                  <div className="font-bold text-accent">{formatCurrency(potentialProfit)}</div>
                </div>
              )}
              {enableStopLoss && enableTakeProfit && (
                <div>
                  <div className="text-muted-foreground">Risk/Reward</div>
                  <div className="font-bold">1:{riskRewardRatio}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Place Order Button */}
        <Button 
          onClick={handlePlaceOrder} 
          disabled={loading || !quantity || (orderType !== "market" && !limitPrice)}
          className="w-full"
          variant={side === "buy" ? "default" : "destructive"}
        >
          {loading ? "Placing Order..." : `Place ${orderType.replace('_', ' ').toUpperCase()} ${side.toUpperCase()} Order`}
        </Button>
      </CardContent>
    </Card>
  );
};
