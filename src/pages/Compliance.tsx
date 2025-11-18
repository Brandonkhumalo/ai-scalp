import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useHasAnyRole } from "@/hooks/useUserRole";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Shield, AlertTriangle, CheckCircle2 } from "lucide-react";
import { format } from "date-fns";
import { AppNavbar } from "@/components/AppNavbar";

interface KYCRecord {
  id: number;
  full_name: string;
  status: string;
  created_at: string;
}

interface AMLAlert {
  id: number;
  alert_type: string;
  severity: string;
  status: string;
  created_at: string;
  details: any;
}

export default function Compliance() {
  const navigate = useNavigate();
  const { hasRole, isLoading } = useHasAnyRole(['admin', 'compliance']);
  const [kycRecords, setKycRecords] = useState<KYCRecord[]>([]);
  const [amlAlerts, setAmlAlerts] = useState<AMLAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !hasRole) {
      navigate('/dashboard');
      return;
    }

    if (hasRole) {
      loadData();
    }
  }, [hasRole, isLoading, navigate]);

  const loadData = async () => {
    try {
      const [kycData, amlData] = await Promise.all([
        apiClient.getKYCRecords(),
        apiClient.getAMLAlerts(),
      ]);

      setKycRecords(kycData || []);
      setAmlAlerts(amlData || []);
    } catch (error) {
      console.error('Error loading compliance data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline', icon: any }> = {
      approved: { variant: 'default', icon: CheckCircle2 },
      pending: { variant: 'secondary', icon: AlertTriangle },
      rejected: { variant: 'destructive', icon: AlertTriangle },
      under_review: { variant: 'outline', icon: AlertTriangle },
      open: { variant: 'destructive', icon: AlertTriangle },
      investigating: { variant: 'secondary', icon: AlertTriangle },
      resolved: { variant: 'default', icon: CheckCircle2 },
    };
    const config = variants[status] || { variant: 'outline', icon: AlertTriangle };
    const Icon = config.icon;
    return (
      <Badge variant={config.variant} className="gap-1">
        <Icon className="h-3 w-3" />
        {status}
      </Badge>
    );
  };

  const getSeverityColor = (severity: string) => {
    const colors: Record<string, string> = {
      low: 'text-blue-500',
      medium: 'text-yellow-500',
      high: 'text-orange-500',
      critical: 'text-red-500',
    };
    return colors[severity] || 'text-gray-500';
  };

  if (isLoading || loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!hasRole) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <div className="p-4">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate('/dashboard')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <Shield className="h-8 w-8" />
            <div>
              <h1 className="text-3xl font-bold">Compliance Dashboard</h1>
              <p className="text-muted-foreground">KYC/AML monitoring and review</p>
            </div>
          </div>

        <Tabs defaultValue="kyc" className="space-y-4">
          <TabsList>
            <TabsTrigger value="kyc">KYC Records</TabsTrigger>
            <TabsTrigger value="aml">AML Alerts</TabsTrigger>
          </TabsList>

          <TabsContent value="kyc" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>KYC Verification Queue</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {kycRecords.map((record) => (
                  <div key={record.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <p className="font-medium">{record.full_name}</p>
                      <p className="text-sm text-muted-foreground">
                        Submitted {format(new Date(record.created_at), 'MMM dd, yyyy')}
                      </p>
                    </div>
                    {getStatusBadge(record.status)}
                  </div>
                ))}
                {kycRecords.length === 0 && (
                  <p className="text-center text-muted-foreground py-8">No KYC records found</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="aml" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>AML Alerts</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {amlAlerts.map((alert) => (
                  <div key={alert.id} className="p-4 border rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className={`h-5 w-5 ${getSeverityColor(alert.severity)}`} />
                        <span className="font-medium capitalize">{alert.alert_type.replace('_', ' ')}</span>
                      </div>
                      {getStatusBadge(alert.status)}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {format(new Date(alert.created_at), 'MMM dd, yyyy HH:mm')}
                    </p>
                    <div className="text-sm bg-muted p-3 rounded">
                      <pre className="whitespace-pre-wrap">{JSON.stringify(alert.details, null, 2)}</pre>
                    </div>
                  </div>
                ))}
                {amlAlerts.length === 0 && (
                  <p className="text-center text-muted-foreground py-8">No AML alerts</p>
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
