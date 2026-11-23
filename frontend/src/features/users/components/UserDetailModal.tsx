import React from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { User } from '@/types/auth';
import { formatDate } from '@/lib/utils';
import { Shield, Mail, Calendar, Key } from 'lucide-react';

interface UserDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
}

export const UserDetailModal: React.FC<UserDetailModalProps> = ({ isOpen, onClose, user }) => {
  if (!user) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="User Profile & RBAC Assignment" maxWidth="lg">
      <div className="space-y-6">
        {/* Header Summary */}
        <div className="flex items-center space-x-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="w-12 h-12 rounded-full bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 font-bold text-lg flex items-center justify-center border border-brand-200 dark:border-brand-800">
            {user.first_name[0]}
            {user.last_name[0]}
          </div>
          <div>
            <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">
              {user.first_name} {user.last_name}
            </h4>
            <div className="flex items-center space-x-2 text-xs text-slate-500 mt-1">
              <Mail className="w-3.5 h-3.5" />
              <span>{user.email}</span>
            </div>
          </div>
          <div className="ml-auto">
            <Badge variant={user.is_active ? 'success' : 'default'}>
              {user.is_active ? 'Active' : 'Inactive'}
            </Badge>
          </div>
        </div>

        {/* Roles & Permissions */}
        <div>
          <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
            <Shield className="w-3.5 h-3.5 text-brand-600" />
            <span>Assigned Platform Roles</span>
          </h5>
          <div className="flex flex-wrap gap-2">
            {user.roles.map((role) => (
              <span
                key={role.name}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-brand-50 text-brand-700 dark:bg-brand-950/80 dark:text-brand-300 border border-brand-200 dark:border-brand-800"
              >
                {role.name}
              </span>
            ))}
          </div>
        </div>

        {/* Identifiers & Metadata */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs bg-slate-50 dark:bg-slate-900 p-4 rounded-lg border border-slate-200 dark:border-slate-800">
          <div>
            <span className="text-slate-400 block mb-0.5">User ID</span>
            <span className="font-mono text-slate-700 dark:text-slate-300 select-all">{user.id}</span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Organization ID</span>
            <span className="font-mono text-slate-700 dark:text-slate-300 select-all">
              {user.organization_id}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500">Created: {formatDate(user.created_at)}</span>
          </div>
          <div className="flex items-center space-x-2">
            <Key className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500">Superuser: {user.is_superuser ? 'Yes' : 'No'}</span>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
};
