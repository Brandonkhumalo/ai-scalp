import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useHasAnyRole } from "@/hooks/useUserRole";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Brain, CheckCircle, XCircle, Clock } from "lucide-react";
import { format } from "date-fns";
import { AppNavbar } from "@/components/AppNavbar";

interface Model {
  id: number;
  model_name: string;
  version: string;
  deployed_at: string;
  status: string;
  approval_status: string;
  performance_metrics: any;
  validation_results: any;
}

export default function ModelRegistry() {
  const navigate = useNavigate();
  const { hasRole, isLoading } = useHasAnyRole(['admin', 'trader', 'operator']);
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !hasRole) {
      navigate('/dashboard');
      return;
    }

    if (hasRole) {
      loadModels();
    }
  }, [hasRole, isLoading, navigate]);

  const loadModels = async () => {
    try {
      const data = await apiClient.getModels();
      setModels(data || []);
    } catch (error) {
      console.error('Error loading models:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      active: 'default',
      shadow: 'secondary',
      deprecated: 'destructive',
      rolled_back: 'outline',
    };
    return <Badge variant={variants[status] || 'outline'}>{status}</Badge>;
  };

  const getApprovalIcon = (status: string) => {
    if (status === 'approved') return <CheckCircle className="h-5 w-5 text-green-500" />;
    if (status === 'rejected') return <XCircle className="h-5 w-5 text-red-500" />;
    return <Clock className="h-5 w-5 text-yellow-500" />;
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
            <Brain className="h-8 w-8" />
            <div>
              <h1 className="text-3xl font-bold">Model Registry</h1>
              <p className="text-muted-foreground">AI model governance and version control</p>
            </div>
          </div>

        <div className="grid gap-4">
          {models.map((model) => (
            <Card key={model.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl">{model.model_name}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">Version {model.version}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {getApprovalIcon(model.approval_status)}
                    {getStatusBadge(model.status)}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Deployed</p>
                    <p className="font-medium">{format(new Date(model.deployed_at), 'MMM dd, yyyy')}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Approval</p>
                    <p className="font-medium capitalize">{model.approval_status}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Status</p>
                    <p className="font-medium capitalize">{model.status}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Version</p>
                    <p className="font-medium">{model.version}</p>
                  </div>
                </div>

                {model.performance_metrics && (
                  <div className="border-t pt-4">
                    <p className="text-sm font-medium mb-2">Performance Metrics</p>
                    <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
                      {JSON.stringify(model.performance_metrics, null, 2)}
                    </pre>
                  </div>
                )}

                {model.validation_results && (
                  <div className="border-t pt-4">
                    <p className="text-sm font-medium mb-2">Validation Results</p>
                    <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
                      {JSON.stringify(model.validation_results, null, 2)}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}

          {models.length === 0 && (
            <Card>
              <CardContent className="text-center py-12">
                <Brain className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">No models registered yet</p>
              </CardContent>
            </Card>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}
