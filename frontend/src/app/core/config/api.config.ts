import { environment } from '../../../environments/environment';

export const API_CONFIG = {
  baseUrl: environment.apiBaseUrl,
  endpoints: {
    auth: {
      login: `${environment.apiBaseUrl}/auth/jwt/login`,
      logout: `${environment.apiBaseUrl}/auth/jwt/logout`,
      register: `${environment.apiBaseUrl}/auth/register`,
      forgotPassword: `${environment.apiBaseUrl}/auth/forgot-password`,
      resetPassword: `${environment.apiBaseUrl}/auth/reset-password`,
    },
    users: {
      me: `${environment.apiBaseUrl}/api/v1/me`,
      fundManagers: `${environment.apiBaseUrl}/api/v1/users/fund-managers`,
    },
    missions: {
      create: `${environment.apiBaseUrl}/api/v1/missions`,
      toApprove: `${environment.apiBaseUrl}/api/v1/missions/to-approve/filter`,
    },
    funds: {
      base: `${environment.apiBaseUrl}/api/v1/funds`,
    },
    refunds: {
      base: `${environment.apiBaseUrl}/api/v1/refunds`,
      byMission: (missionId: string) => `${environment.apiBaseUrl}/api/v1/refunds/by-mission/${missionId}`,
      byId: (refundId: string) => `${environment.apiBaseUrl}/api/v1/refunds/${refundId}`,
      review: (refundId: string) => `${environment.apiBaseUrl}/api/v1/refunds/${refundId}/review`,
      approve: (refundId: string) => `${environment.apiBaseUrl}/api/v1/refunds/${refundId}/approve`,
      receipts: (refundId: string) => `${environment.apiBaseUrl}/api/v1/refunds/${refundId}/receipts`,
      items: (refundId: string) => `${environment.apiBaseUrl}/api/v1/refunds/${refundId}/items`,
    },
  },
} as const;
