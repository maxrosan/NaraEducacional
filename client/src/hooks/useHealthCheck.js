import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
const HEALTH_INTERVAL = 15000;
const HEALTH_TIMEOUT = 8000;
const FAILURES_BEFORE_ALERT = 3;

export function useHealthCheck() {
  const [connected, setConnected] = useState(true);
  const [checking, setChecking] = useState(false);
  const failuresRef = useRef(0);
  const intervalRef = useRef(null);

  const check = useCallback(async () => {
    setChecking(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), HEALTH_TIMEOUT);

      const res = await fetch(`${API_BASE_URL}/api/health/`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        failuresRef.current = 0;
        setConnected(true);
      } else {
        failuresRef.current += 1;
        if (failuresRef.current >= FAILURES_BEFORE_ALERT) setConnected(false);
      }
    } catch {
      failuresRef.current += 1;
      if (failuresRef.current >= FAILURES_BEFORE_ALERT) setConnected(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    check();
    intervalRef.current = setInterval(check, HEALTH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [check]);

  const retry = useCallback(() => {
    check();
  }, [check]);

  return { connected, checking, retry };
}
