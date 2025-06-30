import { apiClient } from './api-client';

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface UserResponse {
  username: string;
}

interface JWTPayload {
  username: string;
  exp: number;
  iat: number;
}

class AuthService {
  private tokenKey = 'jwt_token';
  private expiryKey = 'jwt_expiry';

  async login(username: string, password: string): Promise<TokenResponse> {
    try {
      const response = await apiClient.post<TokenResponse>('/api/v1/auth/login', {
        username,
        password,
      });

      apiClient.setAuthToken(response.access_token);

      const expiryTime = Date.now() + (response.expires_in * 1000);
      localStorage.setItem(this.expiryKey, expiryTime.toString());

      return response;
    } catch (error) {
      throw error;
    }
  }

  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v1/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      this.clearLocalAuth();
    }
  }

  async getCurrentUser(): Promise<UserResponse | null> {
    if (!this.isAuthenticated()) {
      return null;
    }

    try {
      const user = await apiClient.get<UserResponse>('/api/v1/users/info');
      return user;
    } catch (error) {
      console.error('Error fetching current user:', error);
      this.clearLocalAuth();
      return null;
    }
  }

  getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(this.tokenKey);
  }

  isAuthenticated(): boolean {
    if (typeof window === 'undefined') return false;

    const token = this.getToken();
    if (!token) return false;

    const expiry = localStorage.getItem(this.expiryKey);
    if (!expiry) {
      try {
        const payload = this.decodeToken(token);
        if (!payload || !payload.exp) return false;

        const expiryTime = payload.exp * 1000;
        localStorage.setItem(this.expiryKey, expiryTime.toString());
        return Date.now() < expiryTime;
      } catch {
        return false;
      }
    }

    const expiryTime = parseInt(expiry, 10);
    if (Date.now() >= expiryTime) {
      this.clearLocalAuth();
      return false;
    }

    return true;
  }

  getUsernameFromToken(): string | null {
    const token = this.getToken();
    if (!token) return null;

    try {
      const payload = this.decodeToken(token);
      return payload?.username || null;
    } catch {
      return null;
    }
  }

  private decodeToken(token: string): JWTPayload | null {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;

      const payload = parts[1];
      const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(decoded) as JWTPayload;
    } catch {
      return null;
    }
  }

  private clearLocalAuth(): void {
    apiClient.clearAuthToken();
    localStorage.removeItem(this.expiryKey);
  }
}

export const authService = new AuthService();
export default authService;
