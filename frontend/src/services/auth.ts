import request from './request'

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/auth/login', { username, password }),

  register: (data: { username: string; password: string; email?: string }) =>
    request.post('/auth/register', data),

  getMe: () => request.get('/auth/me'),
}
