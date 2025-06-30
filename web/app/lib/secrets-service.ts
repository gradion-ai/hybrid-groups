import { apiClient } from './api-client';

interface Secret {
  name: string;
  created_at?: string;
}

interface SecretCreate {
  name: string;
  value: string;
}

interface SecretsListResponse {
  secrets: Secret[];
}

interface SecretValueResponse {
  name: string;
  value: string;
}

interface MessageResponse {
  message: string;
}

class SecretsService {
  private readonly baseEndpoint = '/api/v1/users/secrets';

  async getSecrets(): Promise<Secret[]> {
    try {
      const response = await apiClient.get<SecretsListResponse>(this.baseEndpoint);
      return response.secrets;
    } catch (error) {
      console.error('Error fetching secrets:', error);
      throw error;
    }
  }

  async getSecretValue(name: string): Promise<string> {
    try {
      const response = await apiClient.get<SecretValueResponse>(`${this.baseEndpoint}/${encodeURIComponent(name)}/value`);
      return response.value;
    } catch (error) {
      console.error('Error fetching secret value:', error);
      throw error;
    }
  }

  async createSecret(data: SecretCreate): Promise<void> {
    try {
      await apiClient.post<MessageResponse>(this.baseEndpoint, data);
    } catch (error) {
      console.error('Error creating secret:', error);
      throw error;
    }
  }

  async updateSecret(name: string, value: string): Promise<void> {
    try {
      await apiClient.put<MessageResponse>(`${this.baseEndpoint}/${encodeURIComponent(name)}`, {
        value,
      });
    } catch (error) {
      console.error('Error updating secret:', error);
      throw error;
    }
  }

  async deleteSecret(name: string): Promise<void> {
    try {
      await apiClient.delete<MessageResponse>(`${this.baseEndpoint}/${encodeURIComponent(name)}`);
    } catch (error) {
      console.error('Error deleting secret:', error);
      throw error;
    }
  }
}

export const secretsService = new SecretsService();
export default secretsService;
