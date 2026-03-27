import { Routes, Route, Navigate } from 'react-router-dom'
import BasicLayout from '../layouts/BasicLayout'
import AuthLayout from '../layouts/AuthLayout'
import Login from '../pages/Login'
import Dashboard from '../pages/Dashboard'
import Monitor from '../pages/Monitor'
import ChartAnalysis from '../pages/ChartAnalysis'
import Indicators from '../pages/Indicators'
import Factors from '../pages/Factors'
import Backtest from '../pages/Backtest'
import AIAnalysis from '../pages/AIAnalysis'
import Settings from '../pages/Settings'
import Logs from '../pages/Logs'
import { useAuthStore } from '../store/auth'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function AppRouter() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <AuthLayout>
            <Login />
          </AuthLayout>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <BasicLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="monitor" element={<Monitor />} />
        <Route path="chart" element={<ChartAnalysis />} />
        <Route path="indicators" element={<Indicators />} />
        <Route path="factors" element={<Factors />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="ai" element={<AIAnalysis />} />
        <Route path="settings" element={<Settings />} />
        <Route path="logs" element={<Logs />} />
      </Route>
    </Routes>
  )
}
