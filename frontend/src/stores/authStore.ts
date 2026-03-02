import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types/api';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  mfaRequired: boolean;
  mfaSessionToken: string | null;

  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  setMfaRequired: (required: boolean, sessionToken?: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      mfaRequired: false,
      mfaSessionToken: null,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true, mfaRequired: false, mfaSessionToken: null }),

      setUser: (user) => set({ user }),

      setMfaRequired: (required, sessionToken) =>
        set({ mfaRequired: required, mfaSessionToken: sessionToken || null }),

      logout: () =>
        set({
          accessToken: null, refreshToken: null, user: null,
          isAuthenticated: false, mfaRequired: false, mfaSessionToken: null,
        }),
    }),
    { name: 'ofmaint-auth' }
  )
);
