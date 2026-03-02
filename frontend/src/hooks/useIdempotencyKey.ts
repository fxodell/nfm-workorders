import { useRef, useCallback } from 'react';

export function useIdempotencyKey() {
  const keyRef = useRef<string | null>(null);

  const generateKey = useCallback(() => {
    keyRef.current = crypto.randomUUID();
    return keyRef.current;
  }, []);

  const getKey = useCallback(() => {
    if (!keyRef.current) {
      keyRef.current = crypto.randomUUID();
    }
    return keyRef.current;
  }, []);

  const resetKey = useCallback(() => {
    keyRef.current = null;
  }, []);

  return { generateKey, getKey, resetKey };
}
