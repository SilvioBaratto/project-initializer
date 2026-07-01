import type { AppEnvironment } from './environment.model';

export const environment: AppEnvironment = {
  apiUrl: 'http://127.0.0.1:8000/api/v1/',
  entraTenantId: 'your-tenant-id',        // set from ENTRA_TENANT_ID
  entraSpaClientId: 'your-spa-client-id', // set from ENTRA_SPA_CLIENT_ID
  authority: 'https://login.microsoftonline.com/your-tenant-id',
  scope: 'api://your-api-client-id/access_as_user',
};
