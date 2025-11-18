import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Activity, Settings, LogOut, Menu, X } from "lucide-react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { apiClient } from "@/lib/api-client";

interface AppNavbarProps {
  className?: string;
}

export const AppNavbar = ({ className = "" }: AppNavbarProps) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userRoles, setUserRoles] = useState<string[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const loadUserRoles = async () => {
      try {
        const meData = await apiClient.getMe();
        setUserRoles(meData.roles || []);
      } catch (error) {
        console.error('Error loading user roles:', error);
      }
    };

    if (apiClient.isAuthenticated()) {
      loadUserRoles();
    }
  }, []);

  const handleLogout = () => {
    apiClient.logout();
    navigate("/");
  };

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const getLinkClass = (path: string) => {
    return isActive(path)
      ? "text-foreground font-semibold"
      : "text-muted-foreground hover:text-foreground transition-smooth";
  };

  return (
    <nav className={`border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50 ${className}`}>
      <div className="container mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6 text-primary" />
            <h1 className="text-lg sm:text-xl font-bold gradient-primary bg-clip-text text-transparent">ZimAI Trader</h1>
          </div>
          
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-4 flex-1 overflow-hidden">
            <div className="flex gap-3 text-sm overflow-x-auto scrollbar-hide whitespace-nowrap flex-1">
              <Link to="/dashboard" className={getLinkClass("/dashboard")}>Dashboard</Link>
              <Link to="/trade" className={getLinkClass("/trade")}>Trade</Link>
              <Link to="/history" className={getLinkClass("/history")}>History</Link>
              <Link to="/balance-history" className={getLinkClass("/balance-history")}>Balance</Link>
              {userRoles && userRoles.includes('admin') && (
                <Link to="/admin" className={getLinkClass("/admin")}>Admin</Link>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Link to="/profile">
                <Button variant="ghost" size="icon">
                  <Settings className="h-5 w-5" />
                </Button>
              </Link>
              <Button variant="ghost" size="icon" onClick={handleLogout}>
                <LogOut className="h-5 w-5" />
              </Button>
            </div>
          </div>

          {/* Mobile Menu Button */}
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {/* Mobile Navigation Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-4 pb-4 border-t border-border pt-4">
            <div className="flex flex-col gap-3">
              <Link to="/dashboard" className={`${getLinkClass("/dashboard")} py-2`} onClick={() => setMobileMenuOpen(false)}>Dashboard</Link>
              <Link to="/trade" className={`${getLinkClass("/trade")} py-2`} onClick={() => setMobileMenuOpen(false)}>Trade</Link>
              <Link to="/history" className={`${getLinkClass("/history")} py-2`} onClick={() => setMobileMenuOpen(false)}>History</Link>
              <Link to="/balance-history" className={`${getLinkClass("/balance-history")} py-2`} onClick={() => setMobileMenuOpen(false)}>Balance History</Link>
              {userRoles && userRoles.includes('admin') && (
                <Link to="/admin" className={`${getLinkClass("/admin")} py-2`} onClick={() => setMobileMenuOpen(false)}>Admin</Link>
              )}
              <div className="flex items-center gap-2 pt-2 border-t border-border mt-2">
                <Link to="/profile" className="flex-1" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="ghost" size="sm" className="w-full">
                    <Settings className="h-4 w-4 mr-2" />
                    Profile
                  </Button>
                </Link>
                <Button variant="ghost" size="sm" className="flex-1" onClick={handleLogout}>
                  <LogOut className="h-4 w-4 mr-2" />
                  Logout
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};
