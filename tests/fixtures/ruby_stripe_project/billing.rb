require 'stripe'

Stripe.api_key = ENV.fetch('STRIPE_SECRET_KEY')

customer = Stripe::Customer.create(
  email: 'user@example.com',
  name: 'Test User'
)

charge = Stripe::Charge.create(
  amount: 2000,
  currency: 'usd',
  customer: customer.id
)
