# Firebase SDK scan skill

## SDK packages
- npm: `firebase` (client SDK — Auth, Firestore, Storage, etc.)
- pypi: `firebase-admin` (server-side Admin SDK)
- npm: `firebase-admin` (Node.js Admin SDK)

## Import patterns

### JavaScript / TypeScript — v9+ modular (current)
```javascript
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs, doc, getDoc } from 'firebase/firestore';
import { getAuth, signInWithEmailAndPassword, onAuthStateChanged } from 'firebase/auth';
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage';
```

### JavaScript / TypeScript — v8 compat (legacy, flag these)
```javascript
import firebase from 'firebase/app';
import 'firebase/firestore';
import 'firebase/auth';
import 'firebase/storage';

// Or with full bundle:
const firebase = require('firebase');
```

### Python (Admin SDK)
```python
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
```

## Call sites to look for

### v9 canonical
- `initializeApp(firebaseConfig)` — app initialization
- `getFirestore(app)` — Firestore client
- `collection(db, 'collectionName')` — collection reference
- `getDocs(query)`, `getDoc(docRef)` — document reads
- `setDoc(docRef, data)`, `addDoc(collection, data)` — writes
- `onSnapshot(query, callback)` — real-time listeners
- `getAuth()`, `signInWithEmailAndPassword(auth, email, password)` — auth
- `onAuthStateChanged(auth, callback)` — auth state listener

### v8 legacy (flag these)
- `firebase.firestore()` — v8 compat init
- `firebase.auth()` — v8 compat init
- `firebase.storage()` — v8 compat init
- `db.collection('name').get()` — v8 chained API
- `db.collection('name').doc('id').set(data)` — v8 chained write
- `firebase.auth().onAuthStateChanged(callback)` — v8 auth

## v8 → v9 key breaking changes
- Full modular API: `firebase.firestore()` → `getFirestore()` (tree-shakeable)
- Collection API: `db.collection('foo')` → `collection(db, 'foo')`
- Document reads: `.get()` → `getDocs()` / `getDoc()`
- Document writes: `.set()` → `setDoc()`
- Auth: `firebase.auth().signIn()` → `signInWithEmailAndPassword(auth, email, password)`
- Real-time: `.onSnapshot()` method chain → `onSnapshot(query, callback)` function call
- v8 compat layer available but deprecated: `import firebase from 'firebase/compat/app'`

## Where to look first
1. `grep("from 'firebase/", "")` — v9 modular import
2. `grep("import firebase from 'firebase", "")` — v8 compat import
3. `grep("initializeApp\|firebase.initializeApp", "")` — app initialization
4. Common locations: `lib/firebase.ts`, `utils/firebase.ts`, `src/config/firebase.ts`

## Anchors (fallback signals)
- Environment variables: `FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_*`, `FIREBASE_SERVICE_ACCOUNT`
- `firebaseConfig` object with `apiKey`, `projectId`, `storageBucket`

## Common wrapper patterns
- `lib/firebase.ts` — app + service singleton exports
- `lib/firebaseAdmin.ts` — Admin SDK singleton (server-side)

## Feeds
- npm: `firebase` package, dist-tag `latest`
- pypi: `firebase-admin` project
- github releases: `firebase/firebase-js-sdk`
- changelog: `https://firebase.google.com/support/release-notes/admin/node`

## What "breaking" means for Firebase
- v8→v9 modular API migration (largest breaking change in Firebase history)
- Service method moves (chained → function-based)
- Auth method signature changes
- Admin SDK: credential format changes, Node.js minimum version
- Firestore query API changes (new `where()` / `orderBy()` function forms)
