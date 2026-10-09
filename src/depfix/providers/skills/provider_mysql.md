# MySQL Client scan skill

## SDK packages
- npm: `mysql` (callback-based, legacy)
- npm: `mysql2` (promise-based, current — often used but separate package)
- pypi: `mysql` (virtual package — redirects to mysql-connector-python)
- pypi: `mysql-connector-python` (Oracle's Python driver)
- pypi: `PyMySQL` (pure Python, widely used)
- rubygems: `mysql`

## Import patterns

### JavaScript / TypeScript
```javascript
// mysql (legacy, callback)
const mysql = require('mysql');
const connection = mysql.createConnection({ host, user, password, database });

// mysql2 (promise API - different package!)
import mysql from 'mysql2/promise';
const connection = await mysql.createConnection({ host, user, password, database });
```

### Python
```python
import mysql.connector
from mysql.connector import connect
import pymysql
```

## Call sites to look for

### mysql (Node.js, callback-based)
- `mysql.createConnection({ host, user, password, database })` — direct connection
- `mysql.createPool({ ... })` — connection pool
- `connection.query('SELECT ...', callback)` — query with callback

### mysql2 (different package, promise-based)
- `await mysql.createConnection({ ... })` — async connection
- `await connection.query('SELECT ...')` — async query
- `await pool.execute('SELECT ...')` — pooled execute

## Where to look first
1. `grep("\"mysql\"\|\"mysql2\"", "package.json")` — package presence
2. `grep("require('mysql\|from 'mysql", "")` — import
3. `grep("createConnection\|createPool", "")` — connection

## Anchors (fallback signals)
- Environment variables: `MYSQL_HOST`, `DB_HOST` with `MYSQL_DATABASE`, `DATABASE_URL` with `mysql://`

## Feeds
- npm: `mysql` package, dist-tag `latest`
- github releases: `mysqljs/mysql`

## What "breaking" means for MySQL clients
- Callback → promise API migration (mysql → mysql2)
- SSL/TLS configuration changes
- Connection pool API changes
- Query result shape changes
