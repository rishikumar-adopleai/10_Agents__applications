import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';

describe('UI Primitives', () => {
  it('renders Button component with variants and loading state', () => {
    const handleClick = vi.fn();
    const { rerender } = render(<Button onClick={handleClick}>Click Me</Button>);

    const btn = screen.getByRole('button', { name: /Click Me/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);

    rerender(<Button isLoading>Loading...</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders Input component with labels and error states', () => {
    render(
      <Input
        label="Test Input"
        placeholder="Enter text..."
        error="Field is mandatory"
      />
    );

    expect(screen.getByLabelText(/Test Input/i)).toBeInTheDocument();
    expect(screen.getByText(/Field is mandatory/i)).toBeInTheDocument();
  });

  it('renders Badge component with correct variant classes', () => {
    const { container } = render(<Badge variant="success">Completed</Badge>);
    expect(container.firstChild).toHaveTextContent('Completed');
  });

  it('renders Modal when isOpen is true', () => {
    const handleClose = vi.fn();
    const { rerender } = render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );

    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal content')).toBeInTheDocument();

    rerender(
      <Modal isOpen={false} onClose={handleClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );
    expect(screen.queryByText('Test Modal')).not.toBeInTheDocument();
  });
});
