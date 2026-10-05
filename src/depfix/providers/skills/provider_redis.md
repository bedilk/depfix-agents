# Redis scan skill

## SDK packages
- npm: `ioredis`, `redis` (node-redis)
- pypi: `redis` (redis-py)
- gem: `redis`

## Import patterns (JS/TS)

```
require('ioredis')
const Redis = require('ioredis')
import Redis from 'ioredis'

require('redis')
const { createClient } = require('redis')
import { createClient } from 'redis'
```

## Bindings & call sites

### ioredis
```javascript
const redis = new Redis(url)
const redis = new Redis({ host, port, password })
redis.get(key)
redis.set(key, value)
redis.set(key, value, 'EX', ttl)
redis.del(key)
redis.publish(channel, message)
redis.subscribe(channel)
redis.pipeline()
redis.multi()
redis.xadd(stream, '*', field, value)    // streams (v4+)
redis.xread('COUNT', n, 'STREAMS', key, id)
```

### node-redis (v4+)
```javascript
const client = createClient({ url })
await client.connect()
client.get(key)
client.set(key, value)
client.set(key, value, { EX: ttl })      // v4 option-object form — different from v3
client.del(key)
client.publish(channel, message)
client.subscribe(channel, listener)      // v4 callback form — different from v3
client.multi()
```

node-redis v3 → v4 is a major breaking change:
- v3: `client.set(key, value, 'EX', ttl)` → v4: `client.set(key, value, { EX: ttl })`
- v3: `client.subscribe(channel)` + `client.on('message', cb)` → v4: `client.subscribe(channel, cb)`
- v4 requires `await client.connect()` before use; v3 auto-connects

### redis-py (Python)
```python
import redis
r = redis.Redis(host, port, db, password)
r.get(key)
r.set(key, value, ex=ttl)
r.pipeline()
r.publish(channel, message)
r.subscribe(channel)
```

### redis gem (Ruby)
```ruby
require 'redis'
redis = Redis.new(url: url)
redis.get(key)
redis.set(key, value, ex: ttl)
redis.publish(channel, message)
redis.subscribe(channel)
redis.pipelined { |pipe| pipe.set(...) }
```

## Where to look first
1. `grep("require\\(['\"]ioredis['\"]\\)|from ['\"]ioredis['\"]", "")` — ioredis is distinctive.
2. `grep("require\\(['\"]redis['\"]\\)|from ['\"]redis['\"]", "")` — node-redis; also picks up redis-py.
3. `find_files("package.json")` — confirm `ioredis` or `redis` in dependencies.
4. Follow the `Redis`/`createClient`/`client`/`redis` binding from the import.

## Do NOT
- Do not report `redis` imports that are dev-only test helpers (e.g. `ioredis-mock`).
- Do not confuse `node-redis` v3 and v4 — the API is not backward-compatible.
  Check `package.json` for the installed version before reporting call-site patterns.
- Do not report `Bull`/`BullMQ`/`Celery` queue imports as redis call sites — they wrap Redis
  but use their own API surface.
