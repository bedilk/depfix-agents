const Sentry = require('@sentry/node');

// v7 transaction API — replaced by startSpan in v8
function processOrder(orderId) {
  const transaction = Sentry.startTransaction({ name: 'process-order', op: 'task' });
  transaction.setStatus('ok');
  const child = transaction.startChild({ op: 'db.query', description: 'SELECT order' });
  child.finish();
  transaction.finish();
}

module.exports = { processOrder };
