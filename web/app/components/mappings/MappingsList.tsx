'use client';

import { useState, useEffect } from 'react';
import { mappingsService } from '../../lib/mappings-service';

interface Mapping {
  id: string;
  key: string;
  value: string;
}

export default function MappingsList() {
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMappings();
  }, []);

  const loadMappings = async () => {
    try {
      setLoading(true);
      setError(null);

      try {
        const mappingsList = await mappingsService.getMappings();
        const convertedMappings = mappingsList.map((mapping: {gateway_name?: string; gateway_username?: string}, index: number) => ({
          id: `mapping_${index}`,
          key: mapping.gateway_name || `gateway.${index}`,
          value: mapping.gateway_username || mapping.gateway_name || `value_${index}`
        }));
        setMappings(convertedMappings);
      } catch {
        console.log('API unavailable');
        setMappings([]);
      }
    } catch (err) {
      console.error('Error loading mappings:', err);
      setError('Failed to load mappings. Please try again.');
      setMappings([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-300 dark:text-gray-400">Loading mappings...</p>
      </div>
    );
  }

  return (
    <div>
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

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-600 dark:divide-gray-700">
          <thead className="bg-gray-700 dark:bg-gray-800">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 dark:text-gray-400 uppercase tracking-wider">
                Key
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-300 dark:text-gray-400 uppercase tracking-wider">
                Value
              </th>
            </tr>
          </thead>
          <tbody className="bg-gray-800 dark:bg-gray-850 divide-y divide-gray-700 dark:divide-gray-750">
            {mappings.length > 0 ? mappings.map((mapping) => (
              <tr key={mapping.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-100 dark:text-gray-200">{mapping.key}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 dark:text-gray-400">{mapping.value}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={2} className="px-6 py-4 text-center text-sm text-gray-400 dark:text-gray-500">
                  No mappings available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
