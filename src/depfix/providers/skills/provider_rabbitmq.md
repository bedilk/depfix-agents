# RabbitMQ Clients scan skill

## SDK packages
- npm: `amqplib` (JavaScript — primary)
- pypi: `pika` (Python — primary)

## Import patterns

### JavaScript / TypeScript
```javascript
import amqplib from 'amqplib';
const amqplib = require('amqplib');
// Channel API
const conn = await amqplib.connect('amqp://localhost');
const channel = await conn.createChannel();
```

### Python
```python
import pika
from pika import BlockingConnection, ConnectionParameters

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
```

## Call sites to look for
- `amqplib.connect(url)` — connection
- `conn.createChannel()` — channel creation
- `channel.assertQueue('name', { durable: true })` — declare queue
- `channel.sendToQueue('name', Buffer.from('message'))` — send
- `channel.consume('name', callback)` — consume
- `channel.publish(exchange, routingKey, content)` — publish to exchange

## Where to look first
1. `grep("amqplib\|pika", "package.json")` — package presence
2. `grep("amqplib.connect\|createChannel", "")` — JS connection
3. `grep("pika.BlockingConnection\|pika.ConnectionParameters", "")` — Python

## Anchors (fallback signals)
- Environment variables: `RABBITMQ_URL`, `AMQP_URL`, `CLOUDAMQP_URL`
- URL: `amqp://`, `amqps://`

## Feeds
- npm: `amqplib` package, dist-tag `latest`
- pypi: `pika` project
- github releases: `amqp-node/amqplib`

## What "breaking" means for RabbitMQ clients
- Channel API shape changes
- Connection option changes
- SSL/TLS configuration API changes
- Python minimum version bumps for pika
