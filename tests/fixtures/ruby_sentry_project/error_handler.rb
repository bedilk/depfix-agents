require 'sentry-ruby'

Sentry.init do |config|
  config.dsn = ENV.fetch('SENTRY_DSN')
  config.traces_sample_rate = 1.0
end

def process_request(params)
  validate(params)
rescue StandardError => e
  Sentry.capture_exception(e)
  nil
end
