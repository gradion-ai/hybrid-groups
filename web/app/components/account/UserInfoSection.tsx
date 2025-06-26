'use client';

import React from 'react';

interface User {
  username: string;
  email?: string;
  id?: string;
}

interface UserInfoSectionProps {
  user: User;
}

const UserInfoSection: React.FC<UserInfoSectionProps> = ({ user }) => {
  const username = user.username;

  return (
    <div className="space-y-4 text-gray-300 dark:text-gray-400">
      <div className="flex items-center space-x-4">
        <img
          src={`https://picsum.photos/seed/${username}/100/100`}
          alt={username}
          className="w-20 h-20 rounded-full object-cover border-2 border-blue-500"
        />
        <div>
          <p className="text-xl font-semibold text-gray-100 dark:text-gray-200">{username}</p>
        </div>
      </div>
    </div>
  );
};

export default UserInfoSection;
