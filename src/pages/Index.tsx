import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArrowRight, Brain, Shield, Zap, TrendingUp, DollarSign, Activity } from "lucide-react";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-trading.jpg";
import aiBrain from "@/assets/ai-brain.jpg";

const Index = () => {
  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm fixed w-full z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6 sm:h-8 sm:w-8 text-primary" />
            <h1 className="text-lg sm:text-2xl font-bold gradient-primary bg-clip-text text-transparent">ZimAI Trader</h1>
          </div>
          <div className="flex gap-2 sm:gap-4">
            <Link to="/auth">
              <Button variant="ghost" size="sm" className="sm:size-default">Sign In</Button>
            </Link>
            <Link to="/auth">
              <Button variant="default" size="sm" className="sm:size-default">Get Started</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-24 sm:pt-32 pb-12 sm:pb-20 px-4 relative overflow-hidden">
        <div className="absolute inset-0 gradient-dark opacity-50"></div>
        <div className="container mx-auto relative z-10">
          <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
            <div className="space-y-4 sm:space-y-6">
              <div className="inline-block px-3 sm:px-4 py-1.5 sm:py-2 bg-primary/10 border border-primary/20 rounded-full">
                <span className="text-xs sm:text-sm text-primary font-semibold">AI-Powered Trading for Zimbabwe</span>
              </div>
              <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-tight">
                Smart Trading,
                <span className="gradient-primary bg-clip-text text-transparent"> Powered by AI</span>
              </h1>
              <p className="text-base sm:text-lg lg:text-xl text-muted-foreground">
                Experience the future of trading with our predictive AI engine. Trade equities with confidence using advanced scalping algorithms designed for quick, consistent profits.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <Link to="/auth" className="w-full sm:w-auto">
                  <Button variant="hero" size="lg" className="w-full sm:w-auto">
                    Start Trading Now <ArrowRight className="ml-2" />
                  </Button>
                </Link>
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  Learn More
                </Button>
              </div>
              <div className="flex flex-wrap gap-6 sm:gap-8 pt-4">
                <div>
                  <div className="text-2xl sm:text-3xl font-bold text-accent">98.5%</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Success Rate</div>
                </div>
                <div>
                  <div className="text-2xl sm:text-3xl font-bold text-accent">$2.5M+</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Volume Traded</div>
                </div>
                <div>
                  <div className="text-2xl sm:text-3xl font-bold text-accent">1,200+</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Active Traders</div>
                </div>
              </div>
            </div>
            <div className="relative mt-8 lg:mt-0">
              <div className="absolute inset-0 gradient-primary opacity-20 blur-3xl"></div>
              <img src={heroImage} alt="Trading Floor" className="rounded-xl sm:rounded-2xl shadow-2xl relative z-10 shadow-glow" />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-12 sm:py-20 px-4 bg-card/30">
        <div className="container mx-auto">
          <div className="text-center mb-12 sm:mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-3 sm:mb-4">Why Choose ZimAI Trader?</h2>
            <p className="text-lg sm:text-xl text-muted-foreground">Advanced technology meets local expertise</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
            <Card className="p-6 sm:p-8 bg-card border-border hover:border-primary transition-smooth">
              <div className="w-14 h-14 sm:w-16 sm:h-16 gradient-primary rounded-2xl flex items-center justify-center mb-4 sm:mb-6 shadow-glow">
                <Brain className="h-7 w-7 sm:h-8 sm:w-8 text-primary-foreground" />
              </div>
              <h3 className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Predictive AI Engine</h3>
              <p className="text-muted-foreground mb-4">
                Our advanced machine learning algorithms analyze market patterns in real-time, predicting 1-15 minute price movements with exceptional accuracy.
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Real-time pattern recognition
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Confidence scoring on every signal
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Continuous learning & optimization
                </li>
              </ul>
            </Card>

            <Card className="p-6 sm:p-8 bg-card border-border hover:border-primary transition-smooth">
              <div className="w-14 h-14 sm:w-16 sm:h-16 gradient-accent rounded-2xl flex items-center justify-center mb-4 sm:mb-6 shadow-profit">
                <TrendingUp className="h-7 w-7 sm:h-8 sm:w-8 text-accent-foreground" />
              </div>
              <h3 className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Paper Trading Integration</h3>
              <p className="text-muted-foreground mb-4">
                Practice with real market data using Alpaca's paper trading environment. No real money at risk while you learn.
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Real-time US stock market data
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Practice trading with virtual funds
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Seamless Alpaca API integration
                </li>
              </ul>
            </Card>

            <Card className="p-6 sm:p-8 bg-card border-border hover:border-primary transition-smooth">
              <div className="w-14 h-14 sm:w-16 sm:h-16 bg-destructive/20 rounded-2xl flex items-center justify-center mb-4 sm:mb-6">
                <Shield className="h-7 w-7 sm:h-8 sm:w-8 text-destructive" />
              </div>
              <h3 className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Advanced Risk Controls</h3>
              <p className="text-muted-foreground mb-4">
                Trade with confidence knowing your capital is protected by multiple layers of risk management and safety controls.
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Daily loss limits
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Position size caps
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
                  Emergency kill switch
                </li>
              </ul>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-12 sm:py-20 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-12 sm:mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-3 sm:mb-4">How It Works</h2>
            <p className="text-lg sm:text-xl text-muted-foreground">Start trading in minutes</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 sm:gap-12 items-center">
            <div className="space-y-6 sm:space-y-8">
              <div className="flex gap-3 sm:gap-4">
                <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 gradient-primary rounded-xl flex items-center justify-center font-bold text-base sm:text-lg">1</div>
                <div>
                  <h3 className="text-lg sm:text-xl font-bold mb-1 sm:mb-2">Create Your Account</h3>
                  <p className="text-muted-foreground">Sign up in seconds with your email or phone number. Complete simple KYC verification.</p>
                </div>
              </div>

              <div className="flex gap-3 sm:gap-4">
                <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 gradient-primary rounded-xl flex items-center justify-center font-bold text-base sm:text-lg">2</div>
                <div>
                  <h3 className="text-lg sm:text-xl font-bold mb-1 sm:mb-2">Connect Your Alpaca Account</h3>
                  <p className="text-muted-foreground">Link your Alpaca paper trading account and start with virtual funds to practice AI-powered trading.</p>
                </div>
              </div>

              <div className="flex gap-3 sm:gap-4">
                <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 gradient-primary rounded-xl flex items-center justify-center font-bold text-base sm:text-lg">3</div>
                <div>
                  <h3 className="text-lg sm:text-xl font-bold mb-1 sm:mb-2">Activate AI Trading</h3>
                  <p className="text-muted-foreground">Enable the AI engine and watch it execute smart trades based on real-time market analysis.</p>
                </div>
              </div>

              <div className="flex gap-3 sm:gap-4">
                <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 gradient-accent rounded-xl flex items-center justify-center font-bold text-base sm:text-lg">4</div>
                <div>
                  <h3 className="text-lg sm:text-xl font-bold mb-1 sm:mb-2">Track & Profit</h3>
                  <p className="text-muted-foreground">Monitor your positions, P&L, and AI signals in real-time from your dashboard.</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 sm:gap-6 mt-8 md:mt-0">
              <img src={aiBrain} alt="AI Engine" className="rounded-lg sm:rounded-xl shadow-lg col-span-2" />
              <Card className="p-4 sm:p-6 flex flex-col justify-center">
                <div className="text-2xl sm:text-3xl font-bold text-accent mb-1 sm:mb-2">90%+</div>
                <div className="text-xs sm:text-sm text-muted-foreground">ML Model Accuracy</div>
              </Card>
              <Card className="p-4 sm:p-6 flex flex-col justify-center">
                <div className="text-2xl sm:text-3xl font-bold text-accent mb-1 sm:mb-2">24/7</div>
                <div className="text-xs sm:text-sm text-muted-foreground">Autonomous Trading</div>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-12 sm:py-20 px-4 relative overflow-hidden">
        <div className="absolute inset-0 gradient-primary opacity-10"></div>
        <div className="container mx-auto relative z-10">
          <Card className="p-8 sm:p-12 text-center bg-card/50 backdrop-blur-sm border-primary/20">
            <Zap className="h-12 w-12 sm:h-16 sm:w-16 text-primary mx-auto mb-4 sm:mb-6" />
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-3 sm:mb-4">Ready to Start Trading?</h2>
            <p className="text-base sm:text-lg lg:text-xl text-muted-foreground mb-6 sm:mb-8 max-w-2xl mx-auto">
              Join thousands of traders using AI to make smarter decisions. Start with paper trading to test the system risk-free.
            </p>
            <Link to="/auth">
              <Button variant="hero" size="lg" className="w-full sm:w-auto">
                Create Free Account <ArrowRight className="ml-2" />
              </Button>
            </Link>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 sm:py-12 px-4 bg-card/30">
        <div className="container mx-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Activity className="h-6 w-6 text-primary" />
                <span className="font-bold text-lg">ZimAI Trader</span>
              </div>
              <p className="text-sm text-muted-foreground">
                AI-powered trading platform for Zimbabwe's equity markets.
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-smooth">Features</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Pricing</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Paper Trading</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-smooth">About Us</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Contact</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Careers</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-smooth">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Terms of Service</a></li>
                <li><a href="#" className="hover:text-foreground transition-smooth">Risk Disclosure</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-border text-center text-sm text-muted-foreground">
            <p>&copy; 2025 ZimAI Trader. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
