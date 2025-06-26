'use client';

import { useAuth } from "./contexts/AuthContext";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="grid grid-rows-[1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <main className="flex flex-col gap-8 items-center">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-4">
            Welcome, {user?.username}
          </h1>
        </div>

        <div className="mb-8 p-6 rounded-lg max-w-md w-full">
          <div>
            <p className="text-lg text-gray-600 text-center">
              You are logged in and ready to use Hybrid Groups.
            </p>
          </div>
        </div>

      </main>

      <footer className="row-start-2 flex gap-6 flex-wrap items-center justify-center">
      </footer>
    </div>
  );
}
