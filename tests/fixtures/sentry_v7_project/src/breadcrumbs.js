const Sentry = require('@sentry/node');

function trackAction(action, userId) {
  Sentry.addBreadcrumb({
    message: action,
    category: 'user.action',
    level: 'info',
    data: { userId }
  });
}

function reportError(err, userId, requestId) {
  Sentry.captureException(err, {
    extra: { requestId },
    user: { id: userId },
    tags: { component: 'checkout' }
  });
}

module.exports = { trackAction, reportError };
