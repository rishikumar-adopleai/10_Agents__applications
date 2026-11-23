import React, { ReactNode } from 'react';
import { AlertCircle, FolderOpen, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export const Spinner: React.FC<{ size?: 'sm' | 'md' | 'lg'; className?: string }> = ({
  size = 'md',
  className = '',
}) => {
  const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' };
  return <Loader2 className={`animate-spin text-brand-600 ${sizes[size]} ${className}`} />;
};

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading data...' }) => (
  <div className="flex flex-col items-center justify-center py-16 text-slate-500 dark:text-slate-400">
    <Spinner size="lg" className="mb-3" />
    <p className="text-sm">{message}</p>
  </div>
);

export const Skeleton: React.FC<{ className?: string }> = ({ className = 'h-4 w-full' }) => (
  <div className={`animate-pulse bg-slate-200 dark:bg-slate-800 rounded ${className}`} />
);

export const ErrorState: React.FC<{
  title?: string;
  message?: string;
  onRetry?: () => void;
}> = ({
  title = 'Something went wrong',
  message = 'An unexpected error occurred while fetching data.',
  onRetry,
}) => (
  <div className="flex flex-col items-center justify-center p-8 text-center bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 rounded-xl my-4">
    <AlertCircle className="w-10 h-10 text-rose-500 mb-3" />
    <h3 className="text-base font-semibold text-rose-900 dark:text-rose-200">{title}</h3>
    <p className="text-sm text-rose-700 dark:text-rose-400 mt-1 max-w-md">{message}</p>
    {onRetry && (
      <Button variant="danger" size="sm" onClick={onRetry} className="mt-4">
        Try Again
      </Button>
    )}
  </div>
);

export const EmptyState: React.FC<{
  title?: string;
  description?: string;
  actionText?: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: ReactNode;
}> = ({
  title = 'No records found',
  description = 'Get started by creating a new entry.',
  actionText,
  actionLabel,
  onAction,
  icon,
}) => {
  const label = actionLabel || actionText;

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-800 rounded-xl my-4">
      <div className="p-3 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded-full mb-3">
        {icon || <FolderOpen className="w-8 h-8" />}
      </div>
      <h3 className="text-base font-medium text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-sm">{description}</p>
      {label && onAction && (
        <Button size="sm" onClick={onAction} className="mt-4">
          {label}
        </Button>
      )}
    </div>
  );
};
