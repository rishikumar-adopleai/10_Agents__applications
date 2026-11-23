import React, { useEffect } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '@/routes/AppRoutes';
import { useAuthStore } from '@/store/authStore';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { User } from '@/types/auth';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
  },
});

export const App: React.FC = () => {
  const { setAuth, setInitialized, isInitialized } = useAuthStore();

  useEffect(() => {
    const initAuth = async () => {
      try {
        const response = await apiClient.get<StandardResponse<User>>('/auth/me');
        if (response.data.data) {
          setAuth(response.data.data, 'cookie-session');
        }
      } catch {
        // Not authenticated
      } finally {
        setInitialized(true);
      }
    };

    if (!isInitialized) {
      initAuth();
    }
  }, [setAuth, setInitialized, isInitialized]);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
