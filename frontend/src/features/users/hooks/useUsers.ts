import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi, ListUsersParams, CreateUserData, UpdateUserData } from '../api/userApi';

export const USER_KEYS = {
  all: ['users'] as const,
  lists: () => [...USER_KEYS.all, 'list'] as const,
  list: (params: ListUsersParams) => [...USER_KEYS.lists(), params] as const,
  details: () => [...USER_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...USER_KEYS.details(), id] as const,
};

export const useUsers = (params: ListUsersParams = { page: 1, page_size: 20 }) => {
  return useQuery({
    queryKey: USER_KEYS.list(params),
    queryFn: () => userApi.listUsers(params),
    placeholderData: (prev) => prev,
  });
};

export const useUser = (userId?: string) => {
  return useQuery({
    queryKey: USER_KEYS.detail(userId || ''),
    queryFn: () => userApi.getUserById(userId!),
    enabled: Boolean(userId),
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateUserData) => userApi.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USER_KEYS.lists() });
    },
  });
};

export const useUpdateUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateUserData }) =>
      userApi.updateUser(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: USER_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: USER_KEYS.detail(variables.id) });
    },
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => userApi.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USER_KEYS.lists() });
    },
  });
};
