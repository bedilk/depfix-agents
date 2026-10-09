# Apache Kafka Clients scan skill

## SDK packages
- npm: `kafkajs` (JavaScript — primary, ~1.2M/month)
- pypi: `kafka-python` (Python — primary)
- pypi: `confluent-kafka` (Confluent's Python client)

## Import patterns

### JavaScript / TypeScript
```javascript
import { Kafka, Partitioners } from 'kafkajs';
const { Kafka } = require('kafkajs');
```

Client construction:
```javascript
const kafka = new Kafka({ clientId: 'my-app', brokers: ['localhost:9092'] });
const producer = kafka.producer();
const consumer = kafka.consumer({ groupId: 'my-group' });
```

### Python
```python
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from confluent_kafka import Producer, Consumer, KafkaException
```

## Call sites to look for
- `kafka.producer()` — producer construction
- `kafka.consumer({ groupId })` — consumer construction
- `await producer.send({ topic, messages })` — send messages
- `await consumer.subscribe({ topics: ['topic'] })` — subscribe
- `await consumer.run({ eachMessage: async ({ topic, partition, message }) => ... })`
- `kafka.admin()` — admin client

## v1 → v2 key breaking changes (kafkajs)
- `new LegacyPartitioner()` removed — use `Partitioners.LegacyPartitioner`
- Default partitioner changed from Legacy to round-robin in v2 (BREAKING: changes message routing!)
- `producer.send()` default partitioner behaviour changed — migration requires explicit `createPartitioner: Partitioners.LegacyPartitioner` to preserve v1 routing
- `consumer.run()` callback signature changes

## Where to look first
1. `grep("kafkajs\|kafka-python\|confluent-kafka", "package.json")` — package presence
2. `grep("new Kafka\b", "")` — Kafka constructor
3. `grep("producer.send\|consumer.subscribe", "")` — primary call sites

## Anchors (fallback signals)
- Environment variables: `KAFKA_BROKERS`, `KAFKA_BOOTSTRAP_SERVERS`
- Broker URL: `localhost:9092`, Confluent Cloud URLs

## Feeds
- npm: `kafkajs` package, dist-tag `latest`
- pypi: `kafka-python` project
- github releases: `tulios/kafkajs`

## What "breaking" means for Kafka clients
- Default partitioner change (v2 — silently breaks message ordering guarantees)
- Consumer group rebalance API changes
- Compression codec support changes
- SASL/SSL authentication API changes
