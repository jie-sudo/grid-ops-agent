// 全局 UI 状态（Zustand）
import { create } from 'zustand';
import type { Role, UserInfo } from '@/types';
import { getStoredUser } from '@/api';

interface AppState {
  user: UserInfo | null;
  setUser: (u: UserInfo | null) => void;
  logout: () => void;
}

const stored = getStoredUser();

export const useAppStore = create<AppState>((set) => ({
  user: stored ? { user_id: stored.user_id, role: stored.role, name: stored.user_id } : null,
  setUser: (u) => set({ user: u }),
  logout: () => set({ user: null }),
}));

export function currentRole(): Role | null {
  return useAppStore.getState().user?.role ?? null;
}
