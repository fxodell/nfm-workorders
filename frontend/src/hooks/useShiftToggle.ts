import { useCallback } from 'react';
import { useUIStore } from '@/stores/uiStore';
import { notificationsApi } from '@/api/notifications';

export function useShiftToggle() {
  const { onShift, setOnShift } = useUIStore();

  const toggleShift = useCallback(async () => {
    const newState = !onShift;
    setOnShift(newState);

    try {
      // Update all area notification prefs
      const response = await notificationsApi.getPrefs();
      const prefs = response.data;

      for (const pref of prefs) {
        await notificationsApi.updatePrefs({
          ...pref,
          on_shift: newState,
        });
      }
    } catch {
      // Revert on failure
      setOnShift(!newState);
    }
  }, [onShift, setOnShift]);

  return { onShift, toggleShift };
}
