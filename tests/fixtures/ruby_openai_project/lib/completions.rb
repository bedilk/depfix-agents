require 'openai/client'

module MyApp
  class Completions
    def initialize
      @client = OpenAI::Client.new
    end

    def call(prompt)
      @client.completions(parameters: { model: 'gpt-3.5-turbo-instruct', prompt: prompt })
    end
  end
end
