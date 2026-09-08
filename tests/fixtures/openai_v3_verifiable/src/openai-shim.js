"use strict";

// Minimal, local stand-in for the "openai" SDK -- avoids depending on a
// real npm package (and any network access) while still giving Verifier's
// real npm/node install+test-run pipeline a genuine pass/fail signal that
// depends on which method a call site actually invokes.
//
// Unlike a real SDK upgrade (which drops the old method), this shim
// exposes both the v3-shaped `createModeration` and the v4-shaped
// `moderations.create` on the same client instance, so this one fixture
// can exercise both outcomes Verifier settles edits to -- "fix migrates
// the call site correctly" (KEPT) and "fix is wrong" (REVERTED) -- by
// varying what src/chat.js calls, without needing two fixture trees.

class Moderations {
  async create({ input } = {}) {
    if (typeof input !== "string" || input.length === 0) {
      throw new TypeError("moderations.create: `input` must be a non-empty string");
    }
    return { results: [{ flagged: false, input }] };
  }
}

class OpenAI {
  constructor(opts = {}) {
    this.apiKey = opts.apiKey;
    this.moderations = new Moderations();
  }

  async createModeration({ input } = {}) {
    if (typeof input !== "string" || input.length === 0) {
      throw new TypeError("createModeration: `input` must be a non-empty string");
    }
    return { data: { results: [{ flagged: false, input }] } };
  }
}

module.exports = { OpenAI };
