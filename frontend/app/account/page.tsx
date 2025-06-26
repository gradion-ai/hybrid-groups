'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/Card';
import UserInfoSection from '../components/account/UserInfoSection';
import MappingsList from '../components/mappings/MappingsList';
import SecretsList from '../components/secrets/SecretsList';

export default function AccountPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/auth/signin');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4 text-gray-100">Loading...</h1>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-gray-100 dark:text-gray-200">Account Management</h1>

      <Card>
        <Card.Header>User Info</Card.Header>
        <Card.Body>
          <UserInfoSection user={user} />
        </Card.Body>
      </Card>

      <Card>
        <Card.Header>Mappings</Card.Header>
        <Card.Body>
          <MappingsList />
        </Card.Body>
      </Card>

      <Card>
        <Card.Header>Secrets</Card.Header>
        <Card.Body>
          <SecretsList />
        </Card.Body>
      </Card>
    </div>
  );
}
