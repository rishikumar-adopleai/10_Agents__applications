import { apiClient } from '@/lib/apiClient';
import { User, RoleEnum } from '@/types/auth';
import { PaginatedResponse, StandardResponse } from '@/types/api';

export interface CreateUserData {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  is_active?: boolean;
  role_names: RoleEnum[];
}

export interface UpdateUserData {
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
  password?: string;
  role_names?: RoleEnum[];
}

export interface ListUsersParams {
  page?: number;
  page_size?: number;
  search?: string;
}

export const userApi = {
  listUsers: async (params?: ListUsersParams): Promise<PaginatedResponse<User>> => {
    const response = await apiClient.get<StandardResponse<PaginatedResponse<User>>>('/users', {
      params,
    });
    return response.data.data;
  },

  getUserById: async (userId: string): Promise<User> => {
    const response = await apiClient.get<StandardResponse<User>>(`/users/${userId}`);
    return response.data.data;
  },

  createUser: async (data: CreateUserData): Promise<User> => {
    const response = await apiClient.post<StandardResponse<User>>('/users', data);
    return response.data.data;
  },

  updateUser: async (userId: string, data: UpdateUserData): Promise<User> => {
    const response = await apiClient.put<StandardResponse<User>>(`/users/${userId}`, data);
    return response.data.data;
  },

  deleteUser: async (userId: string): Promise<boolean> => {
    const response = await apiClient.delete<StandardResponse<{ deleted: boolean }>>(`/users/${userId}`);
    return response.data.data.deleted;
  },
};
