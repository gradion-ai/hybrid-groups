import { apiClient } from './api-client';

interface Mapping {
  gateway_name: string;
  gateway_username: string;
}

interface MappingsListResponse {
  mappings: Mapping[];
}

class MappingsService {
  private readonly baseEndpoint = '/api/v1/users/mappings';

  async getMappings(): Promise<Mapping[]> {
    try {
      const response = await apiClient.get<MappingsListResponse>(this.baseEndpoint);
      return response.mappings;
    } catch (error) {
      console.error('Error fetching mappings:', error);
      throw error;
    }
  }
}

export const mappingsService = new MappingsService();
export default mappingsService;
