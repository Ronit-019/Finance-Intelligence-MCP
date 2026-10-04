export interface User {
  id: number;
  username: string | null;
  email: string;
}

export interface AuthResponse {
  status: string;
  message: string;
  user: User;
  token: string;
}

export interface ChatResponse {
  status: string;
  response: string;
}