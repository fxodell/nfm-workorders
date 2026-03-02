import { create } from 'zustand';

interface UIState {
  sidebarCollapsed: boolean;
  isMobile: boolean;
  onShift: boolean;

  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setIsMobile: (mobile: boolean) => void;
  setOnShift: (onShift: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarCollapsed: false,
  isMobile: window.innerWidth < 768,
  onShift: true,

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setIsMobile: (mobile) => set({ isMobile: mobile }),
  setOnShift: (onShift) => set({ onShift }),
}));
