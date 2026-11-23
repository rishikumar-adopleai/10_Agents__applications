import React, { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/FeedbackStates';
import { User } from '@/types/auth';
import { formatDate } from '@/lib/utils';
import { useUsers, useDeleteUser } from '../hooks/useUsers';
import { UserFormModal } from '../components/UserFormModal';
import { UserDetailModal } from '../components/UserDetailModal';
import {
  UserPlus,
  Search,
  MoreVertical,
  ShieldAlert,
  Edit2,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export const UserListPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  const { data, isLoading, isError, error, refetch } = useUsers({
    page,
    page_size: 15,
    search: search.trim() ? search.trim() : undefined,
  });

  const deleteMutation = useDeleteUser();

  const handleCreate = () => {
    setSelectedUser(null);
    setIsFormOpen(true);
  };

  const handleEdit = (user: User) => {
    setSelectedUser(user);
    setIsFormOpen(true);
  };

  const handleView = (user: User) => {
    setSelectedUser(user);
    setIsDetailOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;
    try {
      await deleteMutation.mutateAsync(userToDelete.id);
      setUserToDelete(null);
    } catch (err) {
      console.error('Failed to delete user:', err);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="User & Access Management"
        description="Provision, monitor, and assign granular RBAC roles for platform operators and domain specialists."
        action={
          <Button onClick={handleCreate} className="shadow-sm">
            <UserPlus className="w-4 h-4 mr-2" />
            Provision User
          </Button>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-brand-500 transition-colors"
          />
        </div>
        <div className="text-xs text-slate-500 font-medium">
          Showing {data?.items.length || 0} of {data?.total || 0} users
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <LoadingState message="Fetching users and RBAC assignments..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to load user records.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No users found"
          description={
            search
              ? `No user matched query "${search}". Try searching another name or email.`
              : 'Start by provisioning your first team member into the organization.'
          }
          actionLabel="Provision User"
          onAction={handleCreate}
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-800/50 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-6">User</th>
                  <th className="py-3 px-6">Assigned Roles</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Joined</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-sm">
                {data.items.map((user) => (
                  <tr
                    key={user.id}
                    className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-3.5 px-6">
                      <div className="flex items-center space-x-3">
                        <div className="w-9 h-9 rounded-full bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 font-bold text-xs flex items-center justify-center shrink-0">
                          {user.first_name[0]}
                          {user.last_name[0]}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900 dark:text-slate-100">
                            {user.first_name} {user.last_name}
                          </p>
                          <p className="text-xs text-slate-500 font-mono">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-6">
                      <div className="flex flex-wrap gap-1.5 max-w-xs">
                        {user.roles.map((r) => (
                          <span
                            key={r.name}
                            className="inline-flex items-center text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-sm border border-slate-200 dark:border-slate-700"
                          >
                            {r.name.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-6">
                      <Badge variant={user.is_active ? 'success' : 'default'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6 text-xs text-slate-500">
                      {formatDate(user.created_at)}
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleView(user)}
                          title="View Details"
                        >
                          <Eye className="w-4 h-4 text-slate-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(user)}
                          title="Edit User"
                        >
                          <Edit2 className="w-4 h-4 text-slate-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setUserToDelete(user)}
                          title="Deactivate / Delete"
                          className="hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                        >
                          <Trash2 className="w-4 h-4 text-slate-400 hover:text-rose-600" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-between px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-xs">
              <span className="text-slate-500">
                Page {data.page} of {data.total_pages}
              </span>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={data.page <= 1}
                >
                  <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={data.page >= data.total_pages}
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      <UserFormModal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        user={selectedUser}
      />

      <UserDetailModal
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        user={selectedUser}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(userToDelete)}
        onClose={() => setUserToDelete(null)}
        title="Confirm User Deactivation"
        maxWidth="md"
      >
        <div className="space-y-4">
          <div className="flex items-start space-x-3 text-slate-600 dark:text-slate-300 text-sm">
            <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <p>
              Are you sure you want to deactivate{' '}
              <strong className="text-slate-900 dark:text-slate-100">
                {userToDelete?.first_name} {userToDelete?.last_name}
              </strong>{' '}
              ({userToDelete?.email})? They will immediately lose access to the platform and active
              sessions will be revoked.
            </p>
          </div>
          <div className="flex justify-end space-x-3 pt-3 border-t border-slate-200 dark:border-slate-800">
            <Button
              variant="outline"
              onClick={() => setUserToDelete(null)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDeleteConfirm}
              isLoading={deleteMutation.isPending}
            >
              Confirm Deactivate
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
