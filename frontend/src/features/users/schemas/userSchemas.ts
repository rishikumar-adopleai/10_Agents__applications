import { z } from 'zod';
import { RoleEnum } from '@/types/auth';

const rolesList: [RoleEnum, ...RoleEnum[]] = [
  'ADMINISTRATOR',
  'SALES_REPRESENTATIVE',
  'SALES_MANAGER',
  'MARKETING_MANAGER',
  'PARTNER_MANAGER',
  'SECURITY_REVIEWER',
  'DELIVERY_OWNER',
];

export const userCreateSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  first_name: z.string().min(1, 'First name is required').max(100),
  last_name: z.string().min(1, 'Last name is required').max(100),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
  role_names: z.array(z.enum(rolesList)).min(1, 'Select at least one role'),
  is_active: z.boolean().default(true),
});

export const userUpdateSchema = z.object({
  first_name: z.string().min(1, 'First name is required').max(100),
  last_name: z.string().min(1, 'Last name is required').max(100),
  password: z.string().min(8, 'Password must be at least 8 characters').optional().or(z.literal('')),
  role_names: z.array(z.enum(rolesList)).min(1, 'Select at least one role'),
  is_active: z.boolean(),
});

export type UserCreateFormValues = z.infer<typeof userCreateSchema>;
export type UserUpdateFormValues = z.infer<typeof userUpdateSchema>;
