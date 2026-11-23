import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserListPage } from '@/features/users/pages/UserListPage';
import { userApi } from '@/features/users/api/userApi';

vi.mock('@/features/users/api/userApi', () => ({
  userApi: {
    listUsers: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
  },
}));

const mockUsersData = {
  items: [
    {
      id: 'usr-123',
      email: 'alex.chen@acme.com',
      first_name: 'Alex',
      last_name: 'Chen',
      organization_id: 'org-default',
      is_active: true,
      is_superuser: false,
      roles: [{ name: 'SALES_REPRESENTATIVE', description: 'Outreach and sales' }],
      created_at: '2026-11-14T10:00:00Z',
      updated_at: '2026-11-14T10:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 15,
  total_pages: 1,
};

describe('UserListPage Reference Feature', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <UserListPage />
      </QueryClientProvider>
    );

  it('renders loading state initially', () => {
    (userApi.listUsers as any).mockReturnValue(new Promise(() => {}));
    renderComponent();

    expect(screen.getByText(/Fetching users and RBAC assignments/i)).toBeInTheDocument();
  });

  it('renders user table with user information and roles upon successful fetch', async () => {
    (userApi.listUsers as any).mockResolvedValue(mockUsersData);
    renderComponent();

    expect(await screen.findByText('Alex Chen')).toBeInTheDocument();
    expect(screen.getByText('alex.chen@acme.com')).toBeInTheDocument();
    expect(screen.getByText('SALES REPRESENTATIVE')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders provision user action button', async () => {
    (userApi.listUsers as any).mockResolvedValue(mockUsersData);
    renderComponent();

    expect(await screen.findByText('Provision User')).toBeInTheDocument();
  });

  it('renders empty state when no users are returned', async () => {
    (userApi.listUsers as any).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 15,
      total_pages: 0,
    });
    renderComponent();

    expect(await screen.findByText(/No users found/i)).toBeInTheDocument();
  });
});
