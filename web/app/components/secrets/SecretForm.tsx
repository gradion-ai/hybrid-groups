'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '../ui/Button';

interface Secret {
  id: string;
  name: string;
  value: string;
}

interface SecretFormProps {
  onSubmit: (secretData: Omit<Secret, 'id'>) => void;
  initialData?: Secret | null;
  error?: string | null;
}

export default function SecretForm({ onSubmit, initialData, error }: SecretFormProps) {
  const [name, setName] = useState('');
  const [value, setValue] = useState('');
  const [errors, setErrors] = useState<{ name?: string; value?: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (initialData) {
      setName(initialData.name);
      setValue('');
    } else {
      setName('');
      setValue('');
    }
    setErrors({});
    setIsSubmitting(false);
  }, [initialData]);

  const validateForm = () => {
    const newErrors: { name?: string; value?: string } = {};

    if (!name.trim()) {
      newErrors.name = 'Secret name is required';
    } else if (name.trim().length > 100) {
      newErrors.name = 'Secret name must be 100 characters or less';
    }

    if (!value.trim()) {
      newErrors.value = 'Secret value is required';
    } else if (value.trim().length > 1000) {
      newErrors.value = 'Secret value must be 1000 characters or less';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      onSubmit({
        name: name.trim(),
        value: value.trim(),
      });
    } catch {
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="p-4 bg-red-900 bg-opacity-50 border border-red-700 rounded-md">
          <p className="text-sm text-red-200">{error}</p>
        </div>
      )}
      <div>
        <label htmlFor="secretName" className="block text-sm font-medium text-gray-200 dark:text-gray-300 mb-1">
          Secret Name
        </label>
        <input
          id="secretName"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={`w-full px-3 py-2 border rounded-md shadow-sm bg-gray-700 dark:bg-gray-800 text-gray-100 dark:text-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm ${
            errors.name ? 'border-red-500' : 'border-gray-600 dark:border-gray-700'
          }`}
          placeholder="Enter a unique name for your secret"
          disabled={isSubmitting}
          autoFocus
        />
        {errors.name && (
          <p className="mt-1 text-sm text-red-400">{errors.name}</p>
        )}
      </div>

      <div>
        <label htmlFor="secretValue" className="block text-sm font-medium text-gray-200 dark:text-gray-300 mb-1">
          {initialData ? 'New Secret Value' : 'Secret Value'}
        </label>
        <textarea
          id="secretValue"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={3}
          className={`w-full px-3 py-2 border rounded-md shadow-sm bg-gray-700 dark:bg-gray-800 text-gray-100 dark:text-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm ${
            errors.value ? 'border-red-500' : 'border-gray-600 dark:border-gray-700'
          }`}
          placeholder="Enter the secret value"
          disabled={isSubmitting}
        />
        {errors.value && (
          <p className="mt-1 text-sm text-red-400">{errors.value}</p>
        )}
      </div>

      <div className="flex gap-3 justify-end pt-4">
        <Button
          type="submit"
          disabled={isSubmitting || !name.trim() || !value.trim()}
          variant="primary"
        >
          {isSubmitting ? (initialData ? 'Updating...' : 'Adding...') : (initialData ? 'Update Secret' : 'Add Secret')}
        </Button>
      </div>
    </form>
  );
}
