import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://819f18d9-5e64-4c3f-acb6-496eb8feee18-00-3uwlbac2sdlrd.spock.replit.dev/api';

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: User;
}

export interface User {
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
    this.loadTokens();
  }

  private async loadTokens() {
    try {
      this.accessToken = await AsyncStorage.getItem('accessToken');
      this.refreshToken = await AsyncStorage.getItem('refreshToken');
    } catch (error) {
      console.error('Error loading tokens:', error);
    }
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<Response> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
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
        await AsyncStorage.setItem('accessToken', data.accessToken);
        return true;
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }

    await this.logout();
    return false;
  }

  async register(
    email: string,
    password: string,
    fullName?: string,
    phone?: string
  ): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        phone,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Registration failed');
    }

    const data = await response.json();
    this.accessToken = data.accessToken;
    this.refreshToken = data.refreshToken;
    await AsyncStorage.setItem('accessToken', data.accessToken);
    await AsyncStorage.setItem('refreshToken', data.refreshToken);
    await AsyncStorage.setItem('user', JSON.stringify(data.user));
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
    await AsyncStorage.setItem('accessToken', data.accessToken);
    await AsyncStorage.setItem('refreshToken', data.refreshToken);
    await AsyncStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }

  async logout(): Promise<void> {
    if (this.accessToken) {
      try {
        await this.request('/auth/logout/', { method: 'POST' });
      } catch (error) {
        console.error('Logout request failed:', error);
      }
    }
    this.accessToken = null;
    this.refreshToken = null;
    await AsyncStorage.removeItem('accessToken');
    await AsyncStorage.removeItem('refreshToken');
    await AsyncStorage.removeItem('user');
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

  async getAlpacaAccount(): Promise<any> {
    const response = await this.request('/alpaca-account/');
    if (!response.ok) {
      throw new Error('Failed to get Alpaca account');
    }
    return response.json();
  }

  async getAlpacaEquityHistory(): Promise<any> {
    const response = await this.request('/alpaca-equity-history/');
    if (!response.ok) {
      throw new Error('Failed to get equity history');
    }
    return response.json();
  }

  async getPerformanceAnalytics(): Promise<any> {
    const response = await this.request('/performance-analytics/');
    if (!response.ok) {
      throw new Error('Failed to get performance analytics');
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

    const cachedUser = await this.getCachedUser();
    if (cachedUser) {
      cachedUser.ai_trading_enabled = data.ai_trading_enabled;
      await AsyncStorage.setItem('user', JSON.stringify(cachedUser));
    }

    return data;
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

  async getTransactions(): Promise<any[]> {
    const response = await this.request('/transactions/');
    if (!response.ok) {
      throw new Error('Failed to get transactions');
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

  async isAuthenticated(): Promise<boolean> {
    if (!this.accessToken) {
      await this.loadTokens();
    }
    return !!this.accessToken;
  }

  async getCachedUser(): Promise<User | null> {
    try {
      const userStr = await AsyncStorage.getItem('user');
      if (!userStr) return null;
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }

  async get(endpoint: string): Promise<any> {
    const response = await this.request(endpoint, { method: 'GET' });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `GET ${endpoint} failed`);
    }
    return response.json();
  }

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
