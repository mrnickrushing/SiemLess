"""
Kafka event ingestion consumer.
Only activated if KAFKA_BOOTSTRAP_SERVERS is set in config.
"""
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        try:
            from app.config import settings
            if not getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", None):
                return
        except Exception:
            return

        try:
            from confluent_kafka import Consumer  # noqa: F401 — check importability
        except ImportError:
            logger.warning("confluent-kafka not installed — Kafka ingestion disabled")
            return

        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("Kafka consumer started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self) -> None:
        from confluent_kafka import Consumer
        from app.config import settings
        from app.database import AsyncSessionLocal
        from app.services.event_store import store_event

        loop = asyncio.get_event_loop()

        consumer_config = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_GROUP_ID,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
        consumer = Consumer(consumer_config)
        consumer.subscribe([settings.KAFKA_TOPIC])

        logger.info(
            "Kafka consumer listening on topic %s (group=%s)",
            settings.KAFKA_TOPIC,
            settings.KAFKA_GROUP_ID,
        )

        try:
            while self._running:
                msg = await loop.run_in_executor(None, consumer.poll, 1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Kafka consumer error: %s", msg.error())
                    continue

                try:
                    raw = msg.value()
                    if isinstance(raw, bytes):
                        data = json.loads(raw.decode("utf-8"))
                    else:
                        data = json.loads(raw)

                    async with AsyncSessionLocal() as db:
                        await store_event(db, data)
                        await db.commit()

                    await loop.run_in_executor(None, consumer.commit)
                    logger.debug("Kafka: ingested event from %s", settings.KAFKA_TOPIC)
                except Exception as exc:
                    logger.error("Failed to process Kafka message: %s", exc)
        finally:
            consumer.close()
            logger.info("Kafka consumer stopped")


kafka_consumer_service = KafkaConsumerService()
