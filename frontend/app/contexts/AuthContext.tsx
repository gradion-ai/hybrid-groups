'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { authService } from '../lib/auth-service';

interface JWTUser {
  username: string;
  email?: string;
}

interface AuthContextType {
  user: JWTUser | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signUp: () => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  isAuthenticated: boolean;
  authMode: 'jwt';
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<JWTUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkJWTAuth = async () => {
      try {
        if (authService.isAuthenticated()) {
          const currentUser = await authService.getCurrentUser();
          if (currentUser) {
            setUser({ username: currentUser.username } as JWTUser);
          } else {
            setUser(null);
          }
        } else {
          setUser(null);
        }
      } catch (error) {
        console.error('Error checking JWT auth:', error);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkJWTAuth();

    const interval = setInterval(() => {
      if (!authService.isAuthenticated()) {
        setUser(null);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const signIn = async (username: string, password: string) => {
    await authService.login(username, password);
    const currentUser = await authService.getCurrentUser();
    if (currentUser) {
      setUser({ username: currentUser.username } as JWTUser);
    }
  };

  const signUp = async () => {
    throw new Error('User registration is only available through the CLI tool');
  };

  const signInWithGoogle = async () => {
    throw new Error('Google sign-in is not supported');
  };

  const signOut = async () => {
    await authService.logout();
    setUser(null);
  };

  const isAuthenticated = authService.isAuthenticated();

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn,
        signUp,
        signInWithGoogle,
        signOut,
        isAuthenticated,
        authMode: 'jwt'
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
