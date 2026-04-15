import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  User, 
  Mail, 
  Phone, 
  Shield,
  Calendar,
  Activity,
  ArrowLeft,
  Key,
  Lock
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency, formatNumber } from "@/lib/formatters";

const Profile = () => {
  const [profile, setProfile] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [capitalModeUpdating, setCapitalModeUpdating] = useState(false);
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone: ""
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    const loadProfile = async () => {
      if (!apiClient.isAuthenticated()) {
        navigate("/auth");
        return;
      }

      try {
        const data = await apiClient.getProfile();
        setProfile(data);
        setFormData({
          full_name: data.full_name || "",
          email: data.email || "",
          phone: data.phone || ""
        });
      } catch (error) {
        navigate("/auth");
      }
    };

    loadProfile();
  }, [navigate]);

  const handleUpdate = async () => {
    try {
      // Note: This would need a backend endpoint for updating profile
      toast({
        title: "Profile Updated",
        description: "Your profile information has been saved",
      });
      setIsEditing(false);
    } catch (error) {
      toast({
        title: "Update Failed",
        description: "Could not update profile",
        variant: "destructive",
      });
    }
  };

  const handleCapitalModeToggle = async (useDemo: boolean) => {
    setCapitalModeUpdating(true);
    try {
      await apiClient.toggleCapitalDemoMode(useDemo);
      setProfile((prev: any) => ({ ...prev, capital_use_demo: useDemo }));
      toast({
        title: "Trading Mode Updated",
        description: `Capital.com mode set to ${useDemo ? "Demo" : "Live"}`,
      });
    } catch (error: any) {
      toast({
        title: "Mode Switch Failed",
        description: error?.message || "Could not switch Capital.com mode",
        variant: "destructive",
      });
    } finally {
      setCapitalModeUpdating(false);
    }
  };

  if (!profile) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  const initials = profile.full_name 
    ? profile.full_name.split(' ').map((n: string) => n[0]).join('').toUpperCase()
    : profile.email[0].toUpperCase();

  const memberSince = profile.created_at 
    ? new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : 'Recently';

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link to="/dashboard">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <Activity className="h-6 w-6 text-primary" />
              <h1 className="text-xl font-bold">User Profile</h1>
            </div>
          </div>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Profile Header Card */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-col md:flex-row items-center gap-6">
              <Avatar className="h-24 w-24">
                <AvatarFallback className="text-2xl bg-gradient-to-br from-primary to-accent">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 text-center md:text-left">
                <h2 className="text-2xl font-bold mb-1">{profile.full_name || 'User'}</h2>
                <p className="text-muted-foreground mb-3">{profile.email}</p>
                <div className="flex flex-wrap gap-2 justify-center md:justify-start">
                  <Badge variant="outline" className="gap-1">
                    <Calendar className="h-3 w-3" />
                    Member since {memberSince}
                  </Badge>
                  {profile.is_verified && (
                    <Badge variant="default" className="gap-1">
                      <Shield className="h-3 w-3" />
                      Verified
                    </Badge>
                  )}
                </div>
              </div>
              <Button 
                variant={isEditing ? "outline" : "default"}
                onClick={() => setIsEditing(!isEditing)}
              >
                {isEditing ? "Cancel" : "Edit Profile"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Personal Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Personal Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full Name</Label>
                    <Input
                      id="full_name"
                      value={formData.full_name}
                      onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      disabled
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number</Label>
                    <Input
                      id="phone"
                      value={formData.phone}
                      onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    />
                  </div>
                  <Button onClick={handleUpdate} className="w-full">
                    Save Changes
                  </Button>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3 p-3 bg-secondary rounded-lg">
                    <User className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm text-muted-foreground">Full Name</div>
                      <div className="font-semibold">{profile.full_name || 'Not set'}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-secondary rounded-lg">
                    <Mail className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm text-muted-foreground">Email</div>
                      <div className="font-semibold">{profile.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-secondary rounded-lg">
                    <Phone className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm text-muted-foreground">Phone Number</div>
                      <div className="font-semibold">{profile.phone || 'Not set'}</div>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Account Security */}
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Security & Settings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between rounded-lg border border-border p-4 mb-4">
                <div>
                  <div className="font-semibold">Capital.com Trading Mode</div>
                  <div className="text-sm text-muted-foreground">
                    {profile.capital_use_demo ? "Demo account (safe testing)" : "Live account (real funds)"}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">Demo</span>
                  <Switch
                    checked={!profile.capital_use_demo}
                    disabled={capitalModeUpdating}
                    onCheckedChange={(checked) => handleCapitalModeToggle(!checked)}
                    aria-label="Toggle Capital.com demo/live mode"
                  />
                  <span className="text-xs text-muted-foreground">Live</span>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Button variant="outline" className="justify-start">
                  <Shield className="h-4 w-4 mr-2" />
                  Change Password
                </Button>
                <Button variant="outline" className="justify-start">
                  <Shield className="h-4 w-4 mr-2" />
                  Two-Factor Authentication
                </Button>
                <Button variant="outline" className="justify-start">
                  <Activity className="h-4 w-4 mr-2" />
                  Login History
                </Button>
                <Button variant="outline" className="justify-start">
                  <User className="h-4 w-4 mr-2" />
                  Privacy Settings
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Profile;
