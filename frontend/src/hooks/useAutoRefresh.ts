import { useState, useEffect, useRef } from 'react';

export function useAutoRefresh(
  callback: () => void | Promise<void>,
  intervalMs: number = 10000,
  enabled: boolean = true
) {
  const [autoRefresh, setAutoRefresh] = useState(enabled);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (autoRefresh && enabled) {
      // Initial call
      callback();
      
      // Set up interval
      intervalRef.current = window.setInterval(() => {
        callback();
      }, intervalMs);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  }, [autoRefresh, enabled, intervalMs, callback]);

  return { autoRefresh, setAutoRefresh };
}

