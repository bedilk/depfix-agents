const Sentry = require('@sentry/node');

// v7 hub/scope API
function tagRequest(userId, region) {
  const hub = Sentry.getCurrentHub();
  hub.configureScope((scope) => {
    scope.setTag('region', region);
    scope.setUser({ id: userId });
  });
}

function isolatedCapture(err, context) {
  Sentry.configureScope((scope) => {
    scope.setExtra('context', context);
  });
  Sentry.captureException(err);
}

module.exports = { tagRequest, isolatedCapture };
