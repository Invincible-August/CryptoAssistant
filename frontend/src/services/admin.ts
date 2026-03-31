import request from './request'

/**
 * Admin-only endpoints (requires JWT for user with role admin).
 */
export const adminApi = {
  /** Hot-reload indicator/factor plugin packages (sys.modules + registries). */
  reloadPlugins: () => request.post('/admin/plugins/reload'),
}
