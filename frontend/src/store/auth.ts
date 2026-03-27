import { create } from 'zustand'

interface User {
  id: number
  username: string
  email: string
  role: string
}

interface AuthState {
  token: string | null
  user: User | null
  setToken: (token: string) => void
  setUser: (user: User) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  user: null,

  setToken: (token: string) => {
    localStorage.setItem('token', token)
    set({ token })
  },

  setUser: (user: User) => set({ user }),

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null })
  },

  isAuthenticated: () => !!get().token,
}))
