"use strict";

const { OpenAI } = require("./openai-shim");

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

module.exports = { openai };
