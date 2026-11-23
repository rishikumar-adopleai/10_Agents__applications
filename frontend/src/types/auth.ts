export type RoleEnum =
  | 'ADMINISTRATOR'
  | 'SALES_REPRESENTATIVE'
  | 'SALES_MANAGER'
  | 'MARKETING_MANAGER'
  | 'PARTNER_MANAGER'
  | 'SECURITY_REVIEWER'
  | 'DELIVERY_OWNER';

export interface UserRole {
  name: RoleEnum;
  description?: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  organization_id: string;
  is_active: boolean;
  is_superuser: boolean;
  roles: UserRole[];
  created_at: string;
  updated_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}
