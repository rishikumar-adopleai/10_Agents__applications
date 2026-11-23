import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { useAuthStore } from '@/store/authStore';
import { apiClient } from '@/lib/apiClient';
import { TokenResponse } from '@/types/auth';
import { StandardResponse } from '@/types/api';
import { ShieldCheck, Sparkles, Key, AlertCircle } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(6, 'Password is required'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { setAuth } = useAuthStore();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const onSubmit = async (values: LoginFormValues) => {
    setErrorMessage(null);
    try {
      const response = await apiClient.post<StandardResponse<TokenResponse>>('/auth/login', {
        email: values.email,
        password: values.password,
      });

      const tokenData = response.data.data;
      setAuth(tokenData.user, tokenData.access_token);
      navigate(from, { replace: true });
    } catch (err: any) {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        'Authentication failed. Please verify credentials.';
      setErrorMessage(msg);
    }
  };

  const handleQuickLogin = (email: string) => {
    setValue('email', email);
    setValue('password', 'AdminPass123!');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <div className="max-w-md w-full space-y-6">
        <div className="text-center">
          <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-2xl flex items-center justify-center mx-auto mb-3 shadow-md">
            Δ
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Enterprise Sales Platform
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Sign in to orchestrate ten specialized enterprise AI agents
          </p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
          {errorMessage && (
            <div className="p-3.5 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-lg flex items-start space-x-2.5 text-xs text-rose-700 dark:text-rose-300">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Work Email"
              type="email"
              placeholder="operator@acme.com"
              error={errors.email?.message}
              {...register('email')}
            />

            <Input
              label="Password"
              type="password"
              placeholder="••••••••••••"
              error={errors.password?.message}
              {...register('password')}
            />

            <Button
              type="submit"
              className="w-full mt-2"
              size="lg"
              isLoading={isSubmitting}
            >
              Sign In to Platform
            </Button>
          </form>

          {/* Quick Demo Accounts */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">
              Seeded Demo Role Profiles
            </span>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleQuickLogin('admin@acme.com')}
                className="p-2 text-left rounded-md bg-slate-50 dark:bg-slate-800 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-colors"
              >
                <span className="font-semibold block">Administrator</span>
                <span className="text-[10px] text-slate-500">admin@acme.com</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('sales.rep@acme.com')}
                className="p-2 text-left rounded-md bg-slate-50 dark:bg-slate-800 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-colors"
              >
                <span className="font-semibold block">Sales Rep</span>
                <span className="text-[10px] text-slate-500">sales.rep@acme.com</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('sales.mgr@acme.com')}
                className="p-2 text-left rounded-md bg-slate-50 dark:bg-slate-800 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-colors"
              >
                <span className="font-semibold block">Sales Manager</span>
                <span className="text-[10px] text-slate-500">sales.mgr@acme.com</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('security@acme.com')}
                className="p-2 text-left rounded-md bg-slate-50 dark:bg-slate-800 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-colors"
              >
                <span className="font-semibold block">Security Reviewer</span>
                <span className="text-[10px] text-slate-500">security@acme.com</span>
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center space-x-2 text-[11px] text-slate-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>Strict Enterprise RBAC & Outbox Architecture Enforced</span>
        </div>
      </div>
    </div>
  );
};
