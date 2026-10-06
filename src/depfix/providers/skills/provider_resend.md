# Resend scan skill

## SDK packages
- npm: `resend`
- pypi: `resend`
- rubygems: `resend`

## Import patterns

### JavaScript / TypeScript
```
import { Resend } from 'resend'
const { Resend } = require('resend')
import Resend from 'resend'
```

### Python
```
from resend import Resend
import resend
```

### Ruby
```
require 'resend'
```

## Call sites
- `new Resend(apiKey)` — constructor (JS/TS)
- `resend.emails.send({from, to, subject, html, text})` — primary sending API
- `resend.emails.batch([...])` — batch send (v2+ API)
- `resend.emails.get(emailId)` — retrieve sent email
- `resend.emails.cancel(emailId)` — cancel scheduled email
- `resend.domains.create(...)`, `resend.domains.list()`
- `resend.contacts.create(...)`, `resend.audiences.create(...)`
- `Resend.new(api_key)` — Ruby constructor

## Migration context: SendGrid → Resend

Many codebases are mid-migration from `@sendgrid/mail` to `resend`.
Flag both packages if found in the same repo:
- old: `import sgMail from '@sendgrid/mail'; sgMail.setApiKey(key); sgMail.send({...})`
- new: `import { Resend } from 'resend'; new Resend(key); resend.emails.send({...})`

## Where to look first
1. `grep("resend", "")` — package name is the identifier, not scoped.
2. `grep("RESEND_API_KEY", "")` — env var is the canonical signal.
3. Email-sending code: `email.service.ts`, `mailer.js`, `notifications/`, `lib/email.ts`.
4. In Python: `from resend import Resend` or `import resend`.
