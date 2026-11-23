import React, { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { User, RoleEnum } from '@/types/auth';
import {
  userCreateSchema,
  userUpdateSchema,
  UserCreateFormValues,
  UserUpdateFormValues,
} from '../schemas/userSchemas';
import { useCreateUser, useUpdateUser } from '../hooks/useUsers';

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: User | null;
}

const AVAILABLE_ROLES: { id: RoleEnum; label: string; desc: string }[] = [
  { id: 'ADMINISTRATOR', label: 'Administrator', desc: 'Full system management and configuration' },
  { id: 'SALES_REPRESENTATIVE', label: 'Sales Representative', desc: 'Outreach, lead response and deal management' },
  { id: 'SALES_MANAGER', label: 'Sales Manager', desc: 'Pipeline tracking and commercial proposals' },
  { id: 'MARKETING_MANAGER', label: 'Marketing Manager', desc: 'Campaigns and AI visibility research' },
  { id: 'PARTNER_MANAGER', label: 'Partner Manager', desc: 'Co-selling, referral tracking and partner enablement' },
  { id: 'SECURITY_REVIEWER', label: 'Security Reviewer', desc: 'Security questionnaires and compliance approvals' },
  { id: 'DELIVERY_OWNER', label: 'Delivery Owner', desc: 'Customer outcomes and proof asset generation' },
];

export const UserFormModal: React.FC<UserFormModalProps> = ({ isOpen, onClose, user }) => {
  const isEditing = Boolean(user);
  const createUserMutation = useCreateUser();
  const updateUserMutation = useUpdateUser();

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<UserCreateFormValues | UserUpdateFormValues>({
    resolver: zodResolver(isEditing ? userUpdateSchema : userCreateSchema),
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      password: '',
      role_names: ['SALES_REPRESENTATIVE'],
      is_active: true,
    },
  });

  useEffect(() => {
    if (user) {
      reset({
        first_name: user.first_name,
        last_name: user.last_name,
        password: '',
        role_names: user.roles.map((r) => r.name),
        is_active: user.is_active,
      });
    } else {
      reset({
        email: '',
        first_name: '',
        last_name: '',
        password: '',
        role_names: ['SALES_REPRESENTATIVE'],
        is_active: true,
      });
    }
  }, [user, reset]);

  const onSubmit = async (values: any) => {
    try {
      if (isEditing && user) {
        const updatePayload: any = {
          first_name: values.first_name,
          last_name: values.last_name,
          role_names: values.role_names,
          is_active: values.is_active,
        };
        if (values.password && values.password.length >= 8) {
          updatePayload.password = values.password;
        }
        await updateUserMutation.mutateAsync({ id: user.id, data: updatePayload });
      } else {
        await createUserMutation.mutateAsync({
          email: values.email,
          first_name: values.first_name,
          last_name: values.last_name,
          password: values.password,
          role_names: values.role_names,
          is_active: values.is_active,
        });
      }
      onClose();
    } catch (err) {
      console.error('Failed to save user:', err);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? `Edit User: ${user?.first_name} ${user?.last_name}` : 'Provision New User'}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {!isEditing && (
          <Input
            label="Email Address"
            type="email"
            placeholder="colleague@acme.com"
            error={(errors as any).email?.message}
            {...register('email' as any)}
          />
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="First Name"
            placeholder="Jane"
            error={errors.first_name?.message}
            {...register('first_name')}
          />
          <Input
            label="Last Name"
            placeholder="Doe"
            error={errors.last_name?.message}
            {...register('last_name')}
          />
        </div>

        <Input
          label={isEditing ? 'New Password (leave empty to keep current)' : 'Password'}
          type="password"
          placeholder="Min 8 characters"
          error={errors.password?.message}
          {...register('password')}
        />

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
            Role Assignments
          </label>
          <Controller
            name="role_names"
            control={control}
            render={({ field }) => (
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 bg-slate-50/50 dark:bg-slate-900/50">
                {AVAILABLE_ROLES.map((role) => {
                  const isChecked = field.value?.includes(role.id);
                  return (
                    <label
                      key={role.id}
                      className="flex items-start space-x-3 p-2 rounded-md hover:bg-white dark:hover:bg-slate-800 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            field.onChange([...(field.value || []), role.id]);
                          } else {
                            field.onChange(
                              (field.value || []).filter((r: RoleEnum) => r !== role.id)
                            );
                          }
                        }}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                      />
                      <div className="text-xs">
                        <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                          {role.label}
                        </span>
                        <span className="text-slate-500 dark:text-slate-400 text-[11px]">
                          {role.desc}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          />
          {errors.role_names && (
            <p className="mt-1 text-xs text-rose-600">{errors.role_names.message as string}</p>
          )}
        </div>

        <div className="flex items-center space-x-2 pt-2">
          <input
            type="checkbox"
            id="is_active"
            {...register('is_active')}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          <label htmlFor="is_active" className="text-xs font-medium text-slate-700 dark:text-slate-300">
            Account is Active
          </label>
        </div>

        <div className="flex justify-end space-x-3 pt-4 border-t border-slate-200 dark:border-slate-800">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            isLoading={isSubmitting || createUserMutation.isPending || updateUserMutation.isPending}
          >
            {isEditing ? 'Save Changes' : 'Create User'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
