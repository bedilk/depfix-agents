# Astro scan skill

## SDK packages
- npm: `astro` (framework — primary)
- npm: `@astrojs/react`, `@astrojs/vue`, `@astrojs/svelte` (integrations)
- npm: `@astrojs/db` (Astro DB)
- npm: `@astrojs/image` (image optimization)

## Import patterns

### JavaScript / TypeScript
```javascript
// Astro component config
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// In .astro files:
import { Image } from 'astro:assets';   // v3+ built-in
import { getCollection } from 'astro:content';
```

### Config file (astro.config.mjs)
```javascript
import { defineConfig } from 'astro/config';
export default defineConfig({
  integrations: [react()],
  output: 'server',
  adapter: node({ mode: 'standalone' }),
});
```

## Call sites to look for
- `defineConfig({ ... })` — astro.config.mjs
- `getCollection('name')` — content collections API
- `getEntry('collection', 'slug')` — single entry
- `import { Image } from 'astro:assets'` — image (v3+)
- `import { actions } from 'astro:actions'` — actions API (v4+)

## Legacy patterns (flag these)
- `import { Image } from '@astrojs/image/components'` → `import { Image } from 'astro:assets'` in v3+
- `import image from '@astrojs/image'` as integration → removed in v3 (built-in now)
- `Astro.glob('**/*.md')` → `getCollection()` preferred since v2
- Content collections v1 schema (Zod-based) vs v2 (loader API in v5)

## v2 → v3 key breaking changes
- `@astrojs/image` integration removed — use built-in `astro:assets`
- `<Image>` from `astro:assets` instead of `@astrojs/image/components`
- Picture component API changed
- View Transitions API added (new, not breaking but significant)
- React/Preact/Vue integrations require explicit `client:*` directive

## v3 → v4 key breaking changes
- `Astro.cookies` API changes
- `getStaticPaths()` type changes
- Actions API introduced

## v4 → v5 key breaking changes
- Content collections v2: new loader API, `defineCollection` with loader
- `astro:content` import paths changed for loader-based collections
- `getCollection()` and `render()` behavior changes

## Where to look first
1. `grep("\"astro\"", "package.json")` — package presence
2. `grep("@astrojs/image", "")` — detect removed integration
3. `grep("astro:assets\|astro:content", "")` — virtual module usage
4. `astro.config.mjs` / `astro.config.ts` — primary config file

## Anchors (fallback signals)
- `.astro` file extensions throughout the project
- `astro.config.mjs` or `astro.config.ts` in project root

## Feeds
- npm: `astro` package, dist-tag `latest`
- github releases: `withastro/astro`

## What "breaking" means for Astro
- Integration removals (e.g., `@astrojs/image` removal in v3)
- Content collections API changes (v5 loader API)
- Config option renames/removals
- Adapter API changes
- Virtual module (`astro:*`) import changes
