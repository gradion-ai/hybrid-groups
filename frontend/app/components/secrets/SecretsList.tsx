'use client';

import React, { useState, useEffect } from 'react';
import { secretsService } from '../../lib/secrets-service';
import { Button } from '../ui/Button';
import Modal from '../ui/Modal';
import SecretForm from './SecretForm';
import { PlusIcon, PencilIcon, TrashIcon, EyeIcon, EyeSlashIcon } from '../ui/Icons';

interface Secret {
  id: string;
  name: string;
  value: string;
}

export default function SecretsList() {
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [secretToDelete, setSecretToDelete] = useState<Secret | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>({});
  const [secretValues, setSecretValues] = useState<Record<string, string>>({});
  const [loadingSecretValues, setLoadingSecretValues] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadSecrets();
  }, []);

  const loadSecrets = async () => {
    try {
      setLoading(true);
      setError(null);

      const secretsList = await secretsService.getSecrets();
      const convertedSecrets = secretsList.map((secret: {name: string}, index: number) => ({
        id: `secret_${index}`,
        name: secret.name,
        value: '••••••••',
      }));
      setSecrets(convertedSecrets);
    } catch (err) {
      console.error('Error loading secrets:', err);
      setError('Failed to load secrets. Please try again.');
    } finally {
      setLoading(false);
    }
  };


  const handleAddSecret = () => {
    setEditingSecret(null);
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleEditSecret = async (secret: Secret) => {
    setModalError(null);
    setEditingSecret({ ...secret, value: '' });
    setIsModalOpen(true);
  };

  const handleDeleteSecret = (id: string) => {
    const secret = secrets.find(s => s.id === id);
    if (secret) {
      setSecretToDelete(secret);
      setIsDeleteModalOpen(true);
    }
  };

  const confirmDeleteSecret = () => {
    if (!secretToDelete) return;

    secretsService.deleteSecret(secretToDelete.name).then(() => {
      setSecretValues(prev => {
        const updated = { ...prev };
        delete updated[secretToDelete.name];
        return updated;
      });
      setVisibleSecrets(prev => {
        const updated = { ...prev };
        delete updated[secretToDelete.id];
        return updated;
      });
      loadSecrets();
    }).catch(err => {
      console.error('Error deleting secret:', err);
      setError('Failed to delete secret. Please try again.');
    });

    setIsDeleteModalOpen(false);
    setSecretToDelete(null);
  };

  const cancelDeleteSecret = () => {
    setIsDeleteModalOpen(false);
    setSecretToDelete(null);
  };

  const handleSaveSecret = (secretData: Omit<Secret, 'id'>) => {
    if (editingSecret) {
      secretsService.updateSecret(editingSecret.name, secretData.value).then(() => {
        setSecretValues(prev => {
          const updated = { ...prev };
          delete updated[editingSecret.name];
          return updated;
        });
        setVisibleSecrets(prev => {
          const updated = { ...prev };
          delete updated[editingSecret.id];
          return updated;
        });
        loadSecrets();
        setIsModalOpen(false);
        setEditingSecret(null);
      }).catch(err => {
        console.error('Error updating secret:', err);
        setModalError('Failed to update secret. Please try again.');
      });
    } else {
      secretsService.createSecret({ name: secretData.name, value: secretData.value }).then(() => {
        loadSecrets();
        setIsModalOpen(false);
        setEditingSecret(null);
      }).catch(err => {
        console.error('Error creating secret:', err);
        setModalError('Failed to create secret. Please try again.');
      });
    }
  };

  const toggleVisibility = async (id: string) => {
    const currentlyVisible = visibleSecrets[id];
    const secret = secrets.find(s => s.id === id);

    if (!secret) return;

    if (loadingSecretValues[secret.name]) return;

    if (!currentlyVisible && !secretValues[secret.name]) {
      setLoadingSecretValues(prev => ({ ...prev, [secret.name]: true }));
      try {
        const secretValue = await secretsService.getSecretValue(secret.name);
        setSecretValues(prev => ({ ...prev, [secret.name]: secretValue }));
      } catch (error) {
        console.error('Error fetching secret value:', error);
        setError('Failed to fetch secret value. Please try again.');
        setLoadingSecretValues(prev => ({ ...prev, [secret.name]: false }));
        return;
      } finally {
        setLoadingSecretValues(prev => ({ ...prev, [secret.name]: false }));
      }
    }

    setVisibleSecrets(prev => ({ ...prev, [id]: !prev[id] }));
  };

  if (loading) {
    return (
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-300 dark:text-gray-400">Loading secrets...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={handleAddSecret} variant="primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Secret
        </Button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-900 bg-opacity-50 border border-red-700 rounded-md">
          <div className="flex items-center">
            <div className="flex flex-col">
              <p className="text-sm font-medium text-red-200">Error</p>
              <p className="text-sm text-red-300">{error}</p>
            </div>
          </div>
        </div>
      )}

      {secrets.length === 0 ? (
        <p className="text-center text-gray-400 dark:text-gray-500 py-4">No secrets configured yet. Click &ldquo;Add Secret&rdquo; to create one.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-600 dark:divide-gray-700">
            <thead className="bg-gray-700 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 dark:text-gray-400 uppercase tracking-wider w-1/4">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 dark:text-gray-400 uppercase tracking-wider w-1/2">Value</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 dark:text-gray-400 uppercase tracking-wider w-1/4">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-gray-800 dark:bg-gray-850 divide-y divide-gray-700 dark:divide-gray-750">
              {secrets.map((secret) => (
                <tr key={secret.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-100 dark:text-gray-200 w-1/4">{secret.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-300 dark:text-gray-400 w-1/2">
                    <div className="flex items-center">
                      <button onClick={() => toggleVisibility(secret.id)} className="mr-2 text-gray-400 hover:text-gray-200 flex-shrink-0">
                        {visibleSecrets[secret.id] ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                      </button>
                      <span className="font-mono break-all overflow-hidden">
                        {visibleSecrets[secret.id] ? (
                          secretValues[secret.name] || secret.value
                        ) : (
                          '••••••••'
                        )}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2 w-1/4">
                    <Button onClick={() => handleEditSecret(secret)} variant="icon" size="sm" aria-label="Edit Secret">
                      <PencilIcon className="w-5 h-5" />
                    </Button>
                    <Button onClick={() => handleDeleteSecret(secret.id)} variant="danger-icon" size="sm" aria-label="Delete Secret">
                      <TrashIcon className="w-5 h-5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => { setIsModalOpen(false); setModalError(null); }} title={editingSecret ? 'Edit Secret' : 'Add New Secret'}>
        <SecretForm onSubmit={handleSaveSecret} initialData={editingSecret} error={modalError} />
      </Modal>

      <Modal isOpen={isDeleteModalOpen} onClose={cancelDeleteSecret} title="Delete Secret">
        <div className="space-y-4">
          <p className="text-gray-300 dark:text-gray-400">
            Are you sure you want to delete the secret <strong className="text-gray-100 dark:text-gray-200">{secretToDelete?.name}</strong>?
          </p>
          <p className="text-red-400 text-sm">
            This action cannot be undone.
          </p>
          <div className="flex space-x-3 justify-end pt-4">
            <Button onClick={cancelDeleteSecret} variant="secondary">
              Cancel
            </Button>
            <Button onClick={confirmDeleteSecret} variant="danger">
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
