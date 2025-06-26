'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../contexts/AuthContext';
import { UserCircleIcon, LogoutIcon } from './ui/Icons';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { user, signOut, isAuthenticated } = useAuth();

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  if (!isAuthenticated || !user) {
    return null;
  }

  const navItems: NavItem[] = [
    {
      path: '/account',
      label: 'Account Management',
      icon: <UserCircleIcon className="w-5 h-5" />
    }
  ];

  const username = user.username;

  return (
    <div className="flex flex-col w-64 bg-gray-800 dark:bg-gray-950 text-gray-100 h-screen">
      <div className="flex items-center justify-center h-20 border-b border-gray-700 dark:border-gray-800">
        <UserCircleIcon className="w-10 h-10 text-blue-500 mr-2" />
        <h1 className="text-xl font-semibold">Hybrid Groups</h1>
      </div>

      <div className="p-4 border-b border-gray-700 dark:border-gray-800">
        <p className="text-sm font-medium text-gray-300 dark:text-gray-400">{username}</p>
      </div>

      <nav className="flex-grow p-4 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link
              key={item.path}
              href={item.path}
              className={`flex items-center px-4 py-2.5 rounded-md text-sm font-medium transition-colors duration-150 ease-in-out cursor-pointer !no-underline hover:!no-underline
                ${isActive
                  ? 'bg-blue-600 !text-white dark:bg-blue-700'
                  : '!text-gray-300 dark:!text-gray-400 hover:bg-gray-700 dark:hover:bg-gray-800 hover:!text-white'}`}
            >
              {item.icon && <span className="mr-3">{item.icon}</span>}
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-gray-700 dark:border-gray-800">
        <button
          onClick={handleSignOut}
          className="flex items-center justify-center w-full px-4 py-2.5 rounded-md text-sm font-medium text-red-400 hover:bg-red-500 hover:text-white transition-colors duration-150 ease-in-out dark:text-red-500 dark:hover:bg-red-600 cursor-pointer"
        >
          <LogoutIcon className="w-5 h-5 mr-2" />
          Logout
        </button>
      </div>

    </div>
  );
};

export default Sidebar;
