'use client';

import React from 'react';
import { cn } from './utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'danger' | 'icon' | 'danger-icon';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-0 transition-colors duration-150 ease-in-out cursor-pointer transform-none translate-x-0 translate-y-0 hover:translate-x-0 hover:translate-y-0';

  const variantStyles = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500',
    secondary: 'bg-gray-600 hover:bg-gray-700 text-gray-100 focus:ring-gray-500 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-200',
    danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500',
    icon: 'text-gray-400 hover:text-gray-200 hover:bg-gray-700 dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-750 focus:ring-blue-500 p-2',
    'danger-icon': 'text-red-400 hover:text-red-200 hover:bg-red-700 dark:text-red-500 dark:hover:text-red-300 dark:hover:bg-red-700 focus:ring-red-500 p-2',
  };

  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  const iconSizeStyles = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-2.5',
  };

  const currentSizeStyle = (variant === 'icon' || variant === 'danger-icon') ? iconSizeStyles[size] : sizeStyles[size];

  return (
    <button
      type="button"
      className={cn(baseStyles, variantStyles[variant], currentSizeStyle, fullWidth ? 'w-full' : '', className)}
      {...props}
    >
      {children}
    </button>
  );
};

export { Button };
