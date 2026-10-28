import { environment } from '../../../environments/environment';

export const API_CONFIG = {
  baseUrl: environment.apiBaseUrl,
  endpoints: {
    auth: {
      login: `${environment.apiBaseUrl}/auth/jwt/login`,
      logout: `${environment.apiBaseUrl}/auth/jwt/logout`,
      register: `${environment.apiBaseUrl}/auth/register`,
    },
    users: {
      me: `${environment.apiBaseUrl}/api/v1/me`,
    },
  },
} as const;
