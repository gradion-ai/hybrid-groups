'use client';

import { useState } from 'react';

interface Secret {
  name: string;
  created_at?: string;
}

interface SecretItemProps {
  secret: Secret;
  onUpdate: (name: string, value: string) => Promise<void>;
  onDelete: (name: string) => Promise<void>;
  isUpdating?: boolean;
  isDeleting?: boolean;
}

export default function SecretItem({
  secret,
  onUpdate,
  onDelete,
  isUpdating = false,
  isDeleting = false
}: SecretItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [newValue, setNewValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleEdit = () => {
    setIsEditing(true);
    setNewValue('');
  };

  const handleSave = async () => {
    if (!newValue.trim()) {
      return;
    }

    setIsProcessing(true);
    try {
      await onUpdate(secret.name, newValue);
      setIsEditing(false);
      setNewValue('');
    } catch {
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setNewValue('');
  };

  const handleDelete = async () => {
    setIsProcessing(true);
    try {
      await onDelete(secret.name);
      setShowDeleteConfirm(false);
    } catch {
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between p-4 border rounded-lg secret-item">
        <div className="flex-1">
          <div className="flex items-center">
            <span className="text-sm font-medium text-gray-900">{secret.name}</span>
            {secret.created_at && (
              <span className="ml-2 text-xs text-gray-500">
                Created: {new Date(secret.created_at).toLocaleDateString()}
              </span>
            )}
          </div>

          {isEditing && (
            <div className="mt-2">
              <input
                type="text"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="Enter new secret value"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                disabled={isProcessing}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSave();
                  } else if (e.key === 'Escape') {
                    handleCancel();
                  }
                }}
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={handleSave}
                  disabled={isProcessing || !newValue.trim()}
                  className="px-3 py-1 bg-blue-600 text-white text-sm rounded disabled:opacity-50 disabled:cursor-not-allowed button-transition"
                  title="Save changes (Enter)"
                >
                  {isProcessing ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={handleCancel}
                  disabled={isProcessing}
                  className="px-3 py-1 bg-gray-300 text-gray-700 text-sm rounded disabled:opacity-50 button-transition"
                  title="Cancel editing (Escape)"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {!isEditing && (
          <div className="flex gap-2 ml-4">
            <button
              onClick={handleEdit}
              disabled={isUpdating || isDeleting}
              className="p-2 text-gray-500 hover:text-blue-600 rounded disabled:opacity-50 button-transition"
              title="Edit secret value"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isUpdating || isDeleting}
              className="p-2 text-gray-500 hover:text-red-600 rounded disabled:opacity-50 button-transition"
              title="Delete secret permanently"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 modal-overlay">
          <div className="bg-white rounded-lg p-6 max-w-sm mx-4 modal-content">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Delete Secret</h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to delete &quot;{secret.name}&quot;? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isProcessing}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md disabled:opacity-50 button-transition"
                title="Keep the secret"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={isProcessing}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md disabled:opacity-50 button-transition"
                title="Permanently delete this secret"
              >
                {isProcessing ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
