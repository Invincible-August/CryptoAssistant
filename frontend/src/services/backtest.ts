import request from './request'

export const backtestApi = {
  run: (data: {
    name: string
    symbol: string
    exchange?: string
    market_type?: string
    timeframe: string
    strategy_config?: Record<string, any>
    start_date: string
    end_date: string
    initial_capital?: number
    fee_rate?: number
    slippage?: number
  }) => request.post('/backtest/run', data),

  listTasks: (limit = 20) =>
    request.get('/backtest/tasks', { params: { limit } }),

  getTask: (taskId: number) => request.get(`/backtest/tasks/${taskId}`),

  getTrades: (taskId: number) =>
    request.get(`/backtest/tasks/${taskId}/trades`),
}
