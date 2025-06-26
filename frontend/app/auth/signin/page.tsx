'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { LoginIcon } from '../../components/ui/Icons';

export default function SignInPage() {
  const router = useRouter();
  const { user, loading, signIn } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSigningIn, setIsSigningIn] = useState(false);

  useEffect(() => {
    if (user && !loading) {
      router.replace('/');
    }
  }, [user, loading, router]);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username.trim() || !password.trim()) {
      setError('Please fill in all fields');
      return;
    }

    try {
      setIsSigningIn(true);
      setError('');
      await signIn(username, password);
      router.push('/');
    } catch (error: unknown) {
      const err = error as { message?: string; response?: { status?: number } };
      if (err.response?.status === 401) {
        setError('Login failed. Please try again.');
      } else {
        setError(err.message || 'An error occurred during login');
      }
      setIsSigningIn(false);
    }
  };


  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-24">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Loading...</h1>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
      <div className="bg-gray-800 p-8 rounded-lg shadow-xl w-full max-w-md">
        <h2 className="text-3xl font-bold text-center text-blue-400 mb-8">Hybrid Groups</h2>

        <form onSubmit={handleSignIn} className="space-y-6">
          {error && (
            <div className="bg-red-900/50 text-red-200 p-3 rounded-md text-sm border border-red-800">
              {error}
            </div>
          )}

          <div>
            <Input
              id="username"
              type="text"
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="bg-gray-700 border-gray-600 text-white placeholder-gray-400"
            />
          </div>

          <div>
            <Input
              id="password"
              type="password"
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="bg-gray-700 border-gray-600 text-white placeholder-gray-400"
            />
          </div>

          <Button type="submit" fullWidth disabled={isSigningIn}>
            <LoginIcon className="w-5 h-5 mr-2" />
            {isSigningIn ? 'Signing in...' : 'Login'}
          </Button>
        </form>

        <p className="text-xs text-gray-500 mt-6 text-center">
          User registration is available through the CLI tool only.
        </p>
      </div>
    </div>
  );
}
