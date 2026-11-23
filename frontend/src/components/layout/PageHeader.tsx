import React, { ReactNode } from 'react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
  actions?: ReactNode;
  breadcrumbs?: Array<{ label: string; href?: string }>;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  action,
  actions,
  breadcrumbs,
}) => {
  const renderedActions = action || actions;

  return (
    <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        {breadcrumbs && (
          <nav className="flex space-x-2 text-xs text-slate-500 mb-1">
            {breadcrumbs.map((b, i) => (
              <span key={i} className="flex items-center space-x-1">
                {i > 0 && <span className="text-slate-300 dark:text-slate-700">/</span>}
                {b.href ? (
                  <a href={b.href} className="hover:underline text-slate-600 dark:text-slate-400">
                    {b.label}
                  </a>
                ) : (
                  <span className="font-medium text-slate-800 dark:text-slate-200">{b.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{title}</h1>
        {description && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>}
      </div>
      {renderedActions && <div className="flex items-center space-x-3">{renderedActions}</div>}
    </div>
  );
};
