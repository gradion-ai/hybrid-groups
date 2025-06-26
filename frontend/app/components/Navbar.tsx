'use client';

import Link from 'next/link';
import { useAuth } from '../contexts/AuthContext';
import BackendStatusIndicator from './BackendStatusIndicator';

export default function Navbar() {
  const { user, signOut, loading, authMode, isAuthenticated } = useAuth();

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  return (
    <nav className="shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="flex-shrink-0 flex items-center">
              <span className="text-xl font-bold">Hybrid Groups</span>
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <BackendStatusIndicator />
            {!loading && (
              <>
                {isAuthenticated && user ? (
                  <div className="flex items-center gap-4">
                    <span className="text-sm">
                      {authMode === 'jwt' && 'username' in user ? user.username : user.email}
                    </span>
                    <Link
                      href="/account"
                      className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                    >
                      Account
                    </Link>
                    <button
                      onClick={handleSignOut}
                      className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium"
                    >
                      Sign Out
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <Link
                      href="/auth/signin"
                      className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
                    >
                      Sign In
                    </Link>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
