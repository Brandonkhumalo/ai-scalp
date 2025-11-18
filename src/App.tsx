import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { TradingProvider } from "./contexts/TradingContext";
import ErrorBoundary from "./components/ErrorBoundary";
import Index from "./pages/Index";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import History from "./pages/History";
import BalanceHistory from "./pages/BalanceHistory";
import Admin from "./pages/Admin";
import AuditLog from "./pages/AuditLog";
import ModelRegistry from "./pages/ModelRegistry";
import Compliance from "./pages/Compliance";
import Trade from "./pages/Trade";
import NotFound from "./pages/NotFound";
import DebugRoles from "./pages/DebugRoles";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

const App = () => (
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <ErrorBoundary>
            <TradingProvider>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/auth" element={<Auth />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/history" element={<History />} />
                <Route path="/balance-history" element={<BalanceHistory />} />
                <Route path="/trade" element={<Trade />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/audit-log" element={<AuditLog />} />
                <Route path="/model-registry" element={<ModelRegistry />} />
                <Route path="/compliance" element={<Compliance />} />
                <Route path="/debug-roles" element={<DebugRoles />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </TradingProvider>
          </ErrorBoundary>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
