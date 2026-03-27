import request from './request'

export const logsApi = {
  getSystemLogs: (params?: { level?: string; module?: string; limit?: number }) =>
    request.get('/logs/system', { params }),

  getErrorLogs: (params?: { module?: string; limit?: number }) =>
    request.get('/logs/errors', { params }),
}
