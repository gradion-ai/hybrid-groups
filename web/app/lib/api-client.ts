import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

interface ApiErrorResponse {
  detail?: string;
  message?: string;
}

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = '') {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = this.getAuthToken();
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error: AxiosError) => {
        return Promise.reject(error);
      }
    );

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ApiErrorResponse>) => {
        if (error.response?.status === 401) {
          this.handleUnauthorized();
        }

        const message = error.response?.data?.detail ||
                       error.response?.data?.message ||
                       error.message ||
                       'An unexpected error occurred';

        return Promise.reject(new Error(message));
      }
    );
  }

  private getAuthToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('jwt_token');
  }

  private handleUnauthorized(): void {
    if (typeof window === 'undefined') return;

    localStorage.removeItem('jwt_token');

    if (window.location.pathname !== '/auth/signin') {
      window.location.href = '/auth/signin';
    }
  }

  setAuthToken(token: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem('jwt_token', token);
  }

  clearAuthToken(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('jwt_token');
  }

  async get<T>(endpoint: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<T>(endpoint, { params });
    return response.data;
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await this.client.post<T>(endpoint, data);
    return response.data;
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await this.client.put<T>(endpoint, data);
    return response.data;
  }

  async delete<T>(endpoint: string): Promise<T> {
    const response = await this.client.delete<T>(endpoint);
    return response.data;
  }

  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<T>(endpoint, data);
    return response.data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;
