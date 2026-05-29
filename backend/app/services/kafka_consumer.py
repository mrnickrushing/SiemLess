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
        """
        Initialize internal state for the KafkaConsumerService.
        
        Sets the background task reference `_task` to `None` and the loop control flag `_running` to `False`.
        """
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """
        Start the background Kafka consume loop if Kafka is configured and the consumer library is available.
        
        This method performs a conditional startup: if `settings.KAFKA_BOOTSTRAP_SERVERS` is set and `confluent_kafka` can be imported, it marks the service as running, schedules the `_consume_loop` as an asyncio background task, and logs that the consumer started. If the bootstrap servers setting is absent or the `confluent_kafka` package is not importable, the method returns without starting the consumer.
        """
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
        """
        Stop the background Kafka consumer loop and wait for its shutdown.
        
        Sets the service's running flag to False, cancels the background task if it exists and is still running, and awaits its completion. A pending cancellation is suppressed (asyncio.CancelledError).
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self) -> None:
        """
        Run the background loop that consumes messages from the configured Kafka topic and persists them to the event store.
        
        Continuously polls the Kafka topic while the service is running, decodes message payloads as JSON (handles both bytes and string payloads), stores each event using the application's async event store within an async DB session, commits the DB transaction, and then commits Kafka offsets. Polling and offset commit operations are executed in a thread executor. Processing errors are logged and do not stop the loop. The Kafka consumer is always closed when the loop exits.
        """
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
