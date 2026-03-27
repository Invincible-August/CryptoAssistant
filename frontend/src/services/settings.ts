import request from './request'

export const settingsApi = {
  listModules: () => request.get('/config/modules'),

  updateModule: (name: string, data: { enabled: boolean; config_json?: any }) =>
    request.put(`/config/modules/${name}`, data),

  getSystem: () => request.get('/config/system'),
}
