import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { UnifiedTradeForm } from "@/components/UnifiedTradeForm";
import { AppNavbar } from "@/components/AppNavbar";

const Trade = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
      <AppNavbar />
      <div className="container mx-auto p-8">
        <div className="mb-6">
          <Link to="/dashboard">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dashboard
            </Button>
          </Link>
        </div>

        <div className="max-w-3xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-2">Trade</h1>
            <p className="text-muted-foreground">
              Execute trades across stocks, options, forex, and crypto using real-time Alpaca data
            </p>
          </div>

          <UnifiedTradeForm />
        </div>
      </div>
    </div>
  );
};

export default Trade;
