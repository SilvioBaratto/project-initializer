import type { AppEnvironment } from './environment.model';

export const environment: AppEnvironment = {
  apiUrl: '/api/v1/',
  entraTenantId: 'your-tenant-id',
  entraSpaClientId: 'your-spa-client-id',
  authority: 'https://login.microsoftonline.com/your-tenant-id',
  scope: 'api://your-api-client-id/access_as_user',
};
