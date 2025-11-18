import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TrendingUp, TrendingDown } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";

export const OptionsChain = () => {
  const { toast } = useToast();
  const [symbol, setSymbol] = useState("AAPL");
  const [expirationDate, setExpirationDate] = useState("");
  const [optionsChain, setOptionsChain] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedOption, setSelectedOption] = useState<any>(null);

  const loadOptionsChain = async () => {
    try {
      setLoading(true);
      const data = await apiClient.alpacaMarketData('getOptionsChain', {
        underlying_symbols: symbol,
        expiration_date: expirationDate || undefined
      });
      
      setOptionsChain(data.options_contracts || []);
      
      if (data.options_contracts?.length === 0) {
        toast({
          title: "No options found",
          description: "No options contracts available for this symbol",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error loading options",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadOptionSnapshot = async (optionSymbol: string) => {
    try {
      const snapshot = await apiClient.alpacaMarketData('getOptionsSnapshot', {
        option_symbol: optionSymbol
      });
      setSelectedOption(snapshot);
    } catch (error: any) {
      console.error('Error loading option snapshot:', error);
    }
  };

  const calls = optionsChain.filter(opt => opt.type === 'call');
  const puts = optionsChain.filter(opt => opt.type === 'put');

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Options Chain</CardTitle>
          <CardDescription>Real-time options data with Greeks and implied volatility</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Underlying Symbol</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
              />
            </div>
            <div className="space-y-2">
              <Label>Expiration Date (Optional)</Label>
              <Input
                type="date"
                value={expirationDate}
                onChange={(e) => setExpirationDate(e.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button onClick={loadOptionsChain} disabled={loading} className="w-full">
                {loading ? 'Loading...' : 'Load Options Chain'}
              </Button>
            </div>
          </div>

          {optionsChain.length > 0 && (
            <Tabs defaultValue="calls" className="mt-6">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="calls">Calls ({calls.length})</TabsTrigger>
                <TabsTrigger value="puts">Puts ({puts.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="calls">
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Strike</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Bid</TableHead>
                        <TableHead>Ask</TableHead>
                        <TableHead>Volume</TableHead>
                        <TableHead>OI</TableHead>
                        <TableHead>IV</TableHead>
                        <TableHead>Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {calls.slice(0, 20).map((option) => (
                        <TableRow key={option.symbol} className="hover:bg-accent/50">
                          <TableCell className="font-medium">${option.strike_price}</TableCell>
                          <TableCell className="text-xs">{option.symbol}</TableCell>
                          <TableCell className="text-green-500">${option.close_price || 'N/A'}</TableCell>
                          <TableCell className="text-red-500">${option.close_price || 'N/A'}</TableCell>
                          <TableCell>{option.volume || 0}</TableCell>
                          <TableCell>{option.open_interest || 0}</TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {option.implied_volatility ? `${(option.implied_volatility * 100).toFixed(1)}%` : 'N/A'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => loadOptionSnapshot(option.symbol)}
                            >
                              Details
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>

              <TabsContent value="puts">
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Strike</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Bid</TableHead>
                        <TableHead>Ask</TableHead>
                        <TableHead>Volume</TableHead>
                        <TableHead>OI</TableHead>
                        <TableHead>IV</TableHead>
                        <TableHead>Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {puts.slice(0, 20).map((option) => (
                        <TableRow key={option.symbol} className="hover:bg-accent/50">
                          <TableCell className="font-medium">${option.strike_price}</TableCell>
                          <TableCell className="text-xs">{option.symbol}</TableCell>
                          <TableCell className="text-green-500">${option.close_price || 'N/A'}</TableCell>
                          <TableCell className="text-red-500">${option.close_price || 'N/A'}</TableCell>
                          <TableCell>{option.volume || 0}</TableCell>
                          <TableCell>{option.open_interest || 0}</TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {option.implied_volatility ? `${(option.implied_volatility * 100).toFixed(1)}%` : 'N/A'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => loadOptionSnapshot(option.symbol)}
                            >
                              Details
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
            </Tabs>
          )}

          {/* Option Details Panel */}
          {selectedOption && (
            <Card className="mt-4 bg-secondary/50">
              <CardHeader>
                <CardTitle className="text-lg">Option Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground">Delta</div>
                    <div className="text-lg font-bold flex items-center gap-1">
                      {selectedOption.greeks?.delta > 0 ? (
                        <TrendingUp className="h-4 w-4 text-green-500" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-red-500" />
                      )}
                      {selectedOption.greeks?.delta?.toFixed(4) || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Gamma</div>
                    <div className="text-lg font-bold">{selectedOption.greeks?.gamma?.toFixed(4) || 'N/A'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Theta</div>
                    <div className="text-lg font-bold">{selectedOption.greeks?.theta?.toFixed(4) || 'N/A'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Vega</div>
                    <div className="text-lg font-bold">{selectedOption.greeks?.vega?.toFixed(4) || 'N/A'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Implied Volatility</div>
                    <div className="text-lg font-bold">
                      {selectedOption.implied_volatility ? `${(selectedOption.implied_volatility * 100).toFixed(2)}%` : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Last Price</div>
                    <div className="text-lg font-bold">${selectedOption.latestQuote?.ap || 'N/A'}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
