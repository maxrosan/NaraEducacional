import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "https://f1cd45481fea6f40f446758638e766f0@o4511038973214720.ingest.us.sentry.io/4511038977343488",
  sendDefaultPii: true,
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),     // optional — records session replays on errors
  ],
  tracesSampleRate: 0.3,            // 30% of transactions — adjust based on traffic
  replaysSessionSampleRate: 0,      // don't record all sessions
  replaysOnErrorSampleRate: 1.0,    // record 100% of sessions that have errors
});

console.log('INSTRUMENT LOADED');