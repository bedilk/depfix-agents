const Sentry = require('@sentry/node');
const express = require('express');
const app = express();

// v7 class-based integrations — all removed in v8
Sentry.init({
  dsn: process.env.SENTRY_DSN,
  tracesSampleRate: 1.0,
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
    new Sentry.Integrations.Express({ app }),
  ],
});

// v7 request/error handler middleware
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());
app.use((err, req, res, next) => Sentry.Handlers.errorHandler()(err, req, res, next));

module.exports = { app };
