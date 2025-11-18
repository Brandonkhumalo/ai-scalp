import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface TickerData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
}

export const LivePriceTicker = () => {
  // Component disabled - no API calls will be made
  return null;
};
