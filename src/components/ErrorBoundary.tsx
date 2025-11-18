import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });

    if (typeof window !== 'undefined' && window.localStorage) {
      const errorLog = {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      };
      
      try {
        const existingLogs = localStorage.getItem('error_logs');
        const logs = existingLogs ? JSON.parse(existingLogs) : [];
        logs.push(errorLog);
        
        if (logs.length > 10) {
          logs.shift();
        }
        
        localStorage.setItem('error_logs', JSON.stringify(logs));
      } catch (e) {
        console.error('Failed to save error log:', e);
      }
    }
  }

  private handleReset = () => {
    if (typeof window !== 'undefined') {
      const shouldClearCache = window.confirm(
        'Would you like to clear the app cache? This may help resolve the issue.'
      );
      
      if (shouldClearCache) {
        localStorage.clear();
        sessionStorage.clear();
      }
      
      window.location.reload();
    }
  };

  private handleGoHome = () => {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 p-8 shadow-2xl">
            <div className="flex items-center gap-4 mb-6">
              <div className="p-3 bg-red-500/20 rounded-full">
                <AlertCircle className="h-8 w-8 text-red-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Something went wrong</h1>
                <p className="text-gray-400 mt-1">
                  The application encountered an unexpected error
                </p>
              </div>
            </div>

            <div className="bg-black/30 rounded-lg p-4 mb-6 border border-white/5">
              <p className="text-sm font-mono text-red-300 mb-2">
                {this.state.error?.message || 'Unknown error'}
              </p>
              {process.env.NODE_ENV === 'development' && this.state.error?.stack && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-300">
                    Stack trace
                  </summary>
                  <pre className="text-xs text-gray-500 mt-2 overflow-auto max-h-40">
                    {this.state.error.stack}
                  </pre>
                </details>
              )}
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                onClick={this.handleReset}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reload Application
              </Button>
              <Button
                onClick={this.handleGoHome}
                variant="outline"
                className="flex-1 border-white/10 text-white hover:bg-white/5"
              >
                Go to Homepage
              </Button>
            </div>

            <div className="mt-6 p-4 bg-blue-500/10 rounded-lg border border-blue-500/20">
              <p className="text-sm text-blue-300">
                <strong>Need help?</strong> The error has been logged. If this persists, please contact support.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
