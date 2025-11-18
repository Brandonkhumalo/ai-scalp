import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useHasAnyRole } from "@/hooks/useUserRole";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, FileText } from "lucide-react";
import { format } from "date-fns";
import { AppNavbar } from "@/components/AppNavbar";

interface AuditLog {
  id: number;
  timestamp: string;
  user_id: number;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: any;
}

export default function AuditLog() {
  const navigate = useNavigate();
  const { hasRole, isLoading } = useHasAnyRole(['admin', 'auditor']);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !hasRole) {
      navigate('/dashboard');
      return;
    }

    if (hasRole) {
      loadLogs();
    }
  }, [hasRole, isLoading, navigate]);

  const loadLogs = async () => {
    try {
      const data = await apiClient.getAuditLogs();
      setLogs(data || []);
    } catch (error) {
      console.error('Error loading audit logs:', error);
    } finally {
      setLoading(false);
    }
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
            <FileText className="h-8 w-8" />
            <div>
              <h1 className="text-3xl font-bold">Audit Log</h1>
              <p className="text-muted-foreground">Immutable record of all system actions</p>
            </div>
          </div>

        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-mono text-sm">
                      {format(new Date(log.timestamp), 'yyyy-MM-dd HH:mm:ss')}
                    </TableCell>
                    <TableCell className="font-medium">{log.action}</TableCell>
                    <TableCell>
                      {log.resource_type}
                      {log.resource_id && <span className="text-muted-foreground ml-2 text-xs">({log.resource_id.slice(0, 8)})</span>}
                    </TableCell>
                    <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                      {JSON.stringify(log.details)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        </div>
      </div>
    </div>
  );
}
