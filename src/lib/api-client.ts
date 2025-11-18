const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: User;
}

interface User {
  id: number;
  email: string;
  username: string;
  full_name: string;
  phone: string;
  usd_balance: number;
  zwl_balance: number;
  ai_trading_enabled: boolean;
  forex_ai_trading_enabled: boolean;
  capital_ai_trading_enabled: boolean;
  roles?: string[];
}

class APIClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.accessToken = localStorage.getItem('accessToken');
    this.refreshToken = localStorage.getItem('refreshToken');
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        return fetch(`${API_BASE_URL}${endpoint}`, {
          ...options,
          headers,
        });
      }
    }

    return response;
  }

  private async refreshAccessToken(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken: this.refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        this.accessToken = data.accessToken;
        localStorage.setItem('accessToken', data.accessToken);
        return true;
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }
    
    this.logout();
    return false;
  }

  async register(
    email: string, 
    password: string, 
    fullName?: string, 
    phone?: string,
    capitalApiKey?: string,
    capitalUsername?: string,
    capitalPassword?: string
  ): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        email, 
        password, 
        full_name: fullName, 
        phone,
        capital_api_key: capitalApiKey,
        capital_username: capitalUsername,
        capital_password: capitalPassword
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Registration failed');
    }

    const data = await response.json();
    this.accessToken = data.accessToken;
    this.refreshToken = data.refreshToken;
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Login failed');
    }

    const data = await response.json();
    this.accessToken = data.accessToken;
    this.refreshToken = data.refreshToken;
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }

  async logout(): Promise<void> {
    if (this.accessToken) {
      await this.request('/auth/logout/', { method: 'POST' });
    }
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
  }

  async getMe(): Promise<{ user: User; roles: string[] }> {
    const response = await this.request('/auth/me/');
    if (!response.ok) {
      throw new Error('Failed to get user');
    }
    return response.json();
  }

  async getProfile(): Promise<any> {
    const response = await this.request('/profile/');
    if (!response.ok) {
      throw new Error('Failed to get profile');
    }
    return response.json();
  }

  async getForexStats(): Promise<any> {
    const response = await this.request('/forex-stats/');
    if (!response.ok) {
      throw new Error('Failed to get forex statistics');
    }
    return response.json();
  }

  async closeForexPosition(dealId: string): Promise<any> {
    const response = await this.request('/close-forex-position/', {
      method: 'POST',
      body: JSON.stringify({ deal_id: dealId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to close position');
    }
    return response.json();
  }

  async getBalanceHistory(): Promise<any> {
    const response = await this.request('/balance-history/');
    if (!response.ok) {
      throw new Error('Failed to get balance history');
    }
    return response.json();
  }

  async getTransactions(): Promise<any[]> {
    const response = await this.request('/transactions/');
    if (!response.ok) {
      throw new Error('Failed to get transactions');
    }
    return response.json();
  }

  async deposit(amount: number, currency: string, paymentMethod: string): Promise<any> {
    const response = await this.request('/deposit/', {
      method: 'POST',
      body: JSON.stringify({ amount, currency, payment_method: paymentMethod }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Deposit failed');
    }
    return response.json();
  }

  async withdraw(amount: number, currency: string, phone: string): Promise<any> {
    const response = await this.request('/withdraw/', {
      method: 'POST',
      body: JSON.stringify({ amount, currency, phone }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Withdrawal failed');
    }
    return response.json();
  }

  async getWithdrawalWallet(): Promise<any> {
    const response = await this.request('/withdrawal-wallet/');
    if (!response.ok) {
      throw new Error('Failed to get withdrawal wallet');
    }
    return response.json();
  }

  async transferToBank(walletId: number, bankName: string, accountNumber: string, accountHolder: string): Promise<any> {
    const response = await this.request('/transfer-to-bank/', {
      method: 'POST',
      body: JSON.stringify({ 
        wallet_id: walletId, 
        bank_name: bankName, 
        account_number: accountNumber, 
        account_holder: accountHolder 
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Bank transfer failed');
    }
    return response.json();
  }

  async redepositFromWallet(walletId: number): Promise<any> {
    const response = await this.request('/redeposit-from-wallet/', {
      method: 'POST',
      body: JSON.stringify({ wallet_id: walletId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Re-deposit failed');
    }
    return response.json();
  }

  async getTrades(): Promise<any[]> {
    const response = await this.request('/trades/');
    if (!response.ok) {
      throw new Error('Failed to get trades');
    }
    return response.json();
  }

  async createTrade(tradeData: any): Promise<any> {
    const response = await this.request('/trades/', {
      method: 'POST',
      body: JSON.stringify(tradeData),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create trade');
    }
    return response.json();
  }

  async closeTrade(tradeId: number, exitPrice: number, profitLoss?: number): Promise<any> {
    const response = await this.request(`/trades/${tradeId}/`, {
      method: 'PATCH',
      body: JSON.stringify({
        exit_price: exitPrice,
        status: 'closed',
        profit_loss: profitLoss
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to close trade');
    }
    return response.json();
  }

  async checkProfitTaking(): Promise<any> {
    const response = await this.request('/check-profit-taking/', {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to check profit taking');
    }
    return response.json();
  }

  async closeProfitableTrades(): Promise<any> {
    const response = await this.request('/close-profitable-trades/', {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to close profitable trades');
    }
    return response.json();
  }

  async getAuditLogs(): Promise<any[]> {
    const response = await this.request('/audit-logs/');
    if (!response.ok) {
      throw new Error('Failed to get audit logs');
    }
    return response.json();
  }

  async getKYCRecords(): Promise<any[]> {
    const response = await this.request('/kyc-records/');
    if (!response.ok) {
      throw new Error('Failed to get KYC records');
    }
    return response.json();
  }

  async getAMLAlerts(): Promise<any[]> {
    const response = await this.request('/aml-alerts/');
    if (!response.ok) {
      throw new Error('Failed to get AML alerts');
    }
    return response.json();
  }

  async getModelRegistry(): Promise<any[]> {
    const response = await this.request('/model-registry/');
    if (!response.ok) {
      throw new Error('Failed to get model registry');
    }
    return response.json();
  }

  async getModels(): Promise<any[]> {
    return this.getModelRegistry();
  }

  async createAuditLog(logData: any): Promise<any> {
    const response = await this.request('/audit-logs/', {
      method: 'POST',
      body: JSON.stringify(logData),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create audit log');
    }
    return response.json();
  }

  async getUsers(): Promise<any[]> {
    const response = await this.request('/users/');
    if (!response.ok) {
      throw new Error('Failed to get users');
    }
    return response.json();
  }

  async assignRole(userId: number, role: string): Promise<void> {
    const response = await this.request('/assign-role/', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, role }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to assign role');
    }
  }

  async removeRole(userId: number, role: string): Promise<void> {
    const response = await this.request('/remove-role/', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, role }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to remove role');
    }
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  getCachedUser(): User | null {
    const userStr = localStorage.getItem('user');
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }

  async toggleAITrading(enabled: boolean): Promise<{ ai_trading_enabled: boolean; message: string }> {
    const response = await this.request('/auth/toggle-ai-trading/', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to toggle AI trading');
    }
    const data = await response.json();
    
    const cachedUser = this.getCachedUser();
    if (cachedUser) {
      cachedUser.ai_trading_enabled = data.ai_trading_enabled;
      localStorage.setItem('user', JSON.stringify(cachedUser));
    }
    
    return data;
  }

  async toggleForexAITrading(enabled: boolean): Promise<{ forex_ai_trading_enabled: boolean; message: string }> {
    const response = await this.request('/auth/toggle-forex-ai-trading/', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to toggle Forex AI trading');
    }
    const data = await response.json();
    
    const cachedUser = this.getCachedUser();
    if (cachedUser) {
      cachedUser.forex_ai_trading_enabled = data.forex_ai_trading_enabled;
      localStorage.setItem('user', JSON.stringify(cachedUser));
    }
    
    return data;
  }

  async alpacaMarketData(action: string, params: any = {}): Promise<any> {
    const response = await this.request('/alpaca-market-data/', {
      method: 'POST',
      body: JSON.stringify({ action, ...params }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Alpaca API request failed');
    }
    return response.json();
  }

  async aiTrading(action: string, params: any = {}): Promise<any> {
    const response = await this.request('/ai-trading/', {
      method: 'POST',
      body: JSON.stringify({ action, ...params }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'AI trading request failed');
    }
    return response.json();
  }

  async analyzeSentiment(symbol: string, instrumentType: string = 'crypto'): Promise<any> {
    return this.aiTrading('analyzeSentiment', { symbol, instrument_type: instrumentType });
  }

  async executeAITrade(symbol: string, instrumentType: string = 'crypto'): Promise<any> {
    return this.aiTrading('executeTrade', { symbol, instrument_type: instrumentType });
  }

  async autoTrade(symbols: string[], instrumentType: string = 'crypto'): Promise<any> {
    return this.aiTrading('autoTrade', { symbols, instrument_type: instrumentType });
  }

  async marketData(action: string, params: any = {}): Promise<any> {
    const response = await this.request('/market-data/', {
      method: 'POST',
      body: JSON.stringify({ action, ...params }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Market data request failed');
    }
    return response.json();
  }

  async getRealtimeQuotes(symbols: string[]): Promise<any> {
    return this.marketData('getRealtimeQuotes', { symbols });
  }

  async getBars(symbol: string, timeframe: string = '5Min', limit: number = 100, useFallback: boolean = true): Promise<any> {
    return this.marketData('getBars', { symbol, timeframe, limit, use_fallback: useFallback });
  }

  async getTrainingData(symbol: string, days: number = 30): Promise<any> {
    return this.marketData('getTrainingData', { symbol, days });
  }

  async getForexRate(base: string, target: string): Promise<any> {
    return this.marketData('getForexRate', { base, target });
  }

  async getForexMajorPairs(): Promise<any> {
    return this.marketData('getForexMajorPairs', {});
  }

  async convertCurrency(amount: number, base: string, target: string): Promise<any> {
    return this.marketData('convertCurrency', { amount, base, target });
  }

  async mlModel(action: string, params: any = {}): Promise<any> {
    const response = await this.request('/ml-model/', {
      method: 'POST',
      body: JSON.stringify({ action, ...params }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'ML model request failed');
    }
    return response.json();
  }

  async trainMLModel(): Promise<any> {
    return this.mlModel('train', {});
  }

  async getMLMetrics(): Promise<any> {
    return this.mlModel('getMetrics', {});
  }

  async autoRetrainML(): Promise<any> {
    return this.mlModel('autoRetrain', {});
  }

  async predictML(features: number[]): Promise<any> {
    return this.mlModel('predict', { features });
  }

  async getCapitalCredentials(): Promise<any> {
    const response = await this.request('/auth/capital-credentials/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to get Capital.com credentials');
    }
    return response.json();
  }

  async updateCapitalCredentials(apiKey: string, username: string, password: string): Promise<any> {
    const response = await this.request('/auth/capital-credentials/', {
      method: 'POST',
      body: JSON.stringify({
        capital_api_key: apiKey,
        capital_username: username,
        capital_password: password
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to update Capital.com credentials');
    }
    return response.json();
  }

  async toggleCapitalDemoMode(useDemo: boolean): Promise<any> {
    const response = await this.request('/auth/capital-credentials/', {
      method: 'POST',
      body: JSON.stringify({
        capital_use_demo: useDemo
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to update Capital.com trading mode');
    }
    return response.json();
  }

  async deleteCapitalCredentials(): Promise<any> {
    const response = await this.request('/auth/capital-credentials/', {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to delete Capital.com credentials');
    }
    return response.json();
  }

  async getCapitalAccountData(): Promise<any> {
    const response = await this.request('/auth/capital-account/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch Capital.com account data');
    }
    return response.json();
  }

  async getAllCapitalAccounts(): Promise<any> {
    const response = await this.request('/auth/capital-accounts/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch Capital.com accounts');
    }
    return response.json();
  }

  async selectCapitalAccount(accountId: string): Promise<any> {
    const response = await this.request('/auth/capital-account/select/', {
      method: 'POST',
      body: JSON.stringify({
        account_id: accountId
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to select Capital.com account');
    }
    return response.json();
  }

  // Capital.com Stock Trading APIs
  async getCapitalStockInstruments(): Promise<any> {
    const response = await this.request('/capital-stock-instruments/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch Capital.com stock instruments');
    }
    return response.json();
  }

  async getCapitalStockPositions(): Promise<any> {
    const response = await this.request('/capital-stock-positions/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch Capital.com stock positions');
    }
    return response.json();
  }

  async getCapitalStockAccountInfo(): Promise<any> {
    const response = await this.request('/capital-stock-account/', {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch Capital.com stock account info');
    }
    return response.json();
  }

  async toggleCapitalStockAI(enabled: boolean): Promise<any> {
    const response = await this.request('/capital-stock-ai-toggle/', {
      method: 'POST',
      body: JSON.stringify({
        enabled: enabled
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to toggle Capital.com stock AI');
    }
    return response.json();
  }

  async closeCapitalStockPosition(dealId: string): Promise<any> {
    const response = await this.request('/capital-stock-close/', {
      method: 'POST',
      body: JSON.stringify({
        deal_id: dealId
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to close Capital.com stock position');
    }
    return response.json();
  }

  // Generic GET method for flexible API calls
  async get(endpoint: string): Promise<any> {
    const response = await this.request(endpoint, {
      method: 'GET',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `GET ${endpoint} failed`);
    }
    return response.json();
  }

  // Generic POST method for flexible API calls
  async post(endpoint: string, data?: any): Promise<any> {
    const response = await this.request(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `POST ${endpoint} failed`);
    }
    return response.json();
  }
}

export const apiClient = new APIClient();
