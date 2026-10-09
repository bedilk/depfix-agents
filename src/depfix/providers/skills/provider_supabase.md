# Supabase scan skill

## SDK packages
- npm: `@supabase/supabase-js`
- pypi: `supabase`

## Import patterns

### JavaScript / TypeScript
```javascript
import { createClient } from '@supabase/supabase-js';
const { createClient } = require('@supabase/supabase-js');
```

Client construction:
```javascript
const supabase = createClient(supabaseUrl, supabaseAnonKey);
const supabase = createClient<Database>(url, key); // with TypeScript generated types
```

### Python
```python
from supabase import create_client, Client
import supabase
```

Client construction:
```python
supabase: Client = create_client(url, key)
```

## Call sites to look for
- `createClient(url, key)` — construction
- `supabase.from('table').select()` — data queries
- `supabase.from('table').insert()` / `.update()` / `.delete()`
- `supabase.auth.signInWithPassword(...)` — auth methods
- `supabase.auth.signInWithOAuth(...)`, `supabase.auth.getUser()`
- `supabase.storage.from('bucket').upload(...)` — storage
- `supabase.functions.invoke(...)` — edge functions

## Legacy v1 call sites (flag these — v1→v2 migration 2022)
- `supabase.auth.signIn({ email, password })` → now `auth.signInWithPassword({ email, password })`
- `supabase.auth.signUp({ email, password })` → still valid but may differ
- `supabase.auth.session()` → now `auth.getSession()`
- `supabase.auth.user()` → now `auth.getUser()`
- `supabase.auth.onAuthStateChange(callback)` → callback signature changed
- `select('*, relation(*)') ` → still valid but embedded resources syntax changed

## v1 → v2 key breaking changes
- Auth method renames: `signIn` → `signInWithPassword` / `signInWithOAuth`
- `auth.session()` → `auth.getSession()` (now async, returns `{data, error}`)
- `auth.user()` → `auth.getUser()` (now async)
- `auth.signOut()` return shape changed
- `realtime` subscription API shape changed (`.on()` signature)
- `postgrest-js` response shape: now `{data, error, count, status, statusText}`

## Where to look first
1. `grep("@supabase/supabase-js", "package.json")` — package presence
2. `grep("createClient", "")` — primary constructor
3. Look in `lib/supabase.ts`, `utils/supabase.ts`, `src/lib/supabaseClient.ts`
4. Auth calls often in `pages/api/auth/`, `app/auth/`, or `lib/auth.ts`

## Anchors (fallback signals)
- URL: `supabase.co` or `*.supabase.co`
- Environment variables: `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_ANON_KEY`

## Common wrapper patterns
- `lib/supabase.ts` exporting a singleton `createClient()` result
- Server-side vs client-side clients (SSR pattern): `createServerClient` from `@supabase/ssr`

## Feeds
- npm: `@supabase/supabase-js` package, dist-tag `latest`
- pypi: `supabase` project
- github releases: `supabase/supabase-js`
- openapi: `https://api.supabase.com/api/v1-json`

## What "breaking" means for Supabase
- Auth method renames (v1→v2 was the big one)
- Response shape changes in postgrest (nested `data.data` → `data`)
- Realtime subscription API changes
- Storage API shape changes
- TypeScript type generation format changes
