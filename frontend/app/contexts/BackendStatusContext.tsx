'use client';

import React, { createContext, useState, useContext, useEffect } from 'react';

type BackendStatus = 'loading' | 'ready' | 'error';

interface BackendStatusContextType {
  status: BackendStatus;
  checkBackendStatus: () => Promise<void>;
}

const BackendStatusContext = createContext<BackendStatusContextType | undefined>(undefined);

export function BackendStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>('loading');

  const checkBackendStatus = async () => {
    setStatus('loading');
    try {
      const response = await fetch('/api/v1/health', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        setStatus('ready');
      } else {
        setStatus('error');
      }
    } catch (error) {
      console.error('Error checking backend status:', error);
      setStatus('error');
    }
  };

  useEffect(() => {
    checkBackendStatus();

    const intervalId = setInterval(checkBackendStatus, 60000); // Check every minute

    return () => clearInterval(intervalId);
  }, []);

  return (
    <BackendStatusContext.Provider value={{ status, checkBackendStatus }}>
      {children}
    </BackendStatusContext.Provider>
  );
}

export function useBackendStatus() {
  const context = useContext(BackendStatusContext);
  if (context === undefined) {
    throw new Error('useBackendStatus must be used within a BackendStatusProvider');
  }
  return context;
}
