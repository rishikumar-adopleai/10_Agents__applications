import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-xl mx-auto my-12 bg-white border border-rose-200 rounded-xl shadow-sm text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
            <AlertCircle className="w-5 h-5" />
          </div>
          <h2 className="text-base font-bold text-slate-900">
            {this.props.fallbackTitle || 'Unable to load this view'}
          </h2>
          <p className="text-xs text-rose-600 font-mono bg-rose-50 p-2.5 rounded-lg border border-rose-100 text-left overflow-x-auto">
            {this.state.error?.message || 'Unknown runtime error occurred'}
          </p>
          <div className="pt-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Reload Page
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
