const API_BASE_URL = 'http://localhost:8000';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  must_change_password: boolean;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface UserInfo {
  email: string;
  is_admin: boolean;
  must_change_password: boolean;
}

// Auth functions
export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });
    if (!response.ok) {
      let errorDetail = 'Login failed';
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorDetail);
    }
    return response.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error('Failed to fetch - Cannot connect to server');
    }
    throw err;
  }
}

export async function changePassword(
  data: ChangePasswordRequest,
  token: string
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Password change failed');
  }
  return response.json();
}

export async function getCurrentUser(token: string): Promise<UserInfo> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error('Failed to get user info');
  }
  return response.json();
}

// Stats functions
export async function getProvidersStats(token: string) {
  const response = await fetch(`${API_BASE_URL}/v1/stats/providers`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Failed to fetch provider stats');
  return response.json();
}

export async function getProvidersTimeseries(
  token: string,
  windowMinutes: number = 60,
  stepSeconds: number = 60
) {
  const response = await fetch(
    `${API_BASE_URL}/v1/stats/providers/timeseries?window_minutes=${windowMinutes}&step_seconds=${stepSeconds}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  if (!response.ok) throw new Error('Failed to fetch timeseries');
  return response.json();
}

export async function getKeyStats(token: string) {
  const response = await fetch(`${API_BASE_URL}/v1/stats/keys`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Failed to fetch key stats');
  return response.json();
}

export async function getKeyErrors(token: string) {
  const response = await fetch(`${API_BASE_URL}/v1/stats/keys/errors`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Failed to fetch key errors');
  return response.json();
}

export async function getRunsStats(token: string, windowMinutes: number = 60) {
  const response = await fetch(
    `${API_BASE_URL}/v1/stats/runs?window_minutes=${windowMinutes}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  if (!response.ok) throw new Error('Failed to fetch runs stats');
  return response.json();
}

export async function getRecentErrors(token: string, limit: number = 50) {
  const response = await fetch(
    `${API_BASE_URL}/v1/stats/errors/recent?limit=${limit}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  if (!response.ok) throw new Error('Failed to fetch recent errors');
  return response.json();
}

