export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  message?: string;
  detail?: string;
}
