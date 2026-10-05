require 'net/http'
require 'json'

class ApiService
  def initialize
    openai = MyApp::InternalClient.new
    stripe = MyApp::PaymentClient.new
    @clients = { openai: openai, stripe: stripe }
  end

  def fetch(name)
    @clients[name]&.call
  end
end
