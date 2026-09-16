import 'regenerator-runtime/runtime';
import '@/lib/pwaInstallPrompt';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import App from '@/App';
import '@/index.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { Toaster } from '@/components/ui/toaster';
import { useHealthCheck } from '@/hooks/useHealthCheck';
import { ConnectionLostModal } from '@/components/ConnectionLostModal';

function HealthCheck() {
  const { connected, checking, retry } = useHealthCheck();
  return <ConnectionLostModal open={!connected} checking={checking} onRetry={retry} />;
}
import * as Sentry from "@sentry/react";
import "./instrument"

ReactDOM.createRoot(document.getElementById('root'),
{
  // Callback called when an error is thrown and not caught by an ErrorBoundary.
  onUncaughtError: Sentry.reactErrorHandler((error, errorInfo) => {
    console.warn("Uncaught error", error, errorInfo.componentStack);
  }),
  // Callback called when React catches an error in an ErrorBoundary.
  onCaughtError: Sentry.reactErrorHandler(),
  // Callback called when React automatically recovers from errors.
  onRecoverableError: Sentry.reactErrorHandler(),
}
).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <HelmetProvider>
        <AuthProvider>
          <App />
          <HealthCheck />
          <Toaster />
        </AuthProvider>
      </HelmetProvider>
    </BrowserRouter>
  </React.StrictMode>
);
