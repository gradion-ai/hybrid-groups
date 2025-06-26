'use client';

import React from 'react';
import { useBackendStatus } from '../contexts/BackendStatusContext';

export default function BackendStatusIndicator() {
  const { status, checkBackendStatus } = useBackendStatus();

  const getStatusStyles = () => {
    switch (status) {
      case 'ready':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      case 'loading':
      default:
        return 'bg-yellow-500 animate-pulse';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'ready':
        return 'Backend ready';
      case 'error':
        return 'Backend error';
      case 'loading':
      default:
        return 'Loading backend...';
    }
  };

  return (
    <div className="flex items-center space-x-2">
      <div
        className={`w-2.5 h-2.5 rounded-full ${getStatusStyles()}`}
        title={getStatusText()}
      />
      <span className="text-xs text-gray-400">{getStatusText()}</span>
      {status === 'error' && (
        <button
          onClick={() => checkBackendStatus()}
          className="text-xs text-blue-500 hover:text-blue-400"
          title="Retry connection"
        >
          Retry
        </button>
      )}
    </div>
  );
}
