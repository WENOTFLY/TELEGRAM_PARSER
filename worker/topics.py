from __future__ import annotations

"""Utilities for grouping messages into topics and computing rankings.

This module provides three main entry points:

``cluster_topics``
    Groups recent messages into similarity-based topics and stores the
    associations in the ``topics`` and ``topic_messages`` tables.

``compute_ranking``
    Calculates popularity/trend based ranking scores for both messages and
    topics over a set of time windows.

``schedule_jobs``
    Launches periodic tasks for refreshing topics and recomputing rankings.
    The caller must supply a ``sessionmaker`` which is used to create short
    lived database sessions for each run.

The clustering and ranking algorithms are intentionally lightweight and rely on
built-in Python modules to avoid heavy dependencies.  They provide reasonable
behaviour for tests and small installations while remaining easy to replace with
more sophisticated implementations later.
"""

from datetime import datetime, timedelta
import asyncio
import logging
from difflib import SequenceMatcher
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from web.models import Message, Ranking, Topic, TopicMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topic clustering
# ---------------------------------------------------------------------------

def _similarity(a: str | None, b: str | None) -> float:
    """Return a simple ratio between two strings.

    The function falls back to ``0`` if either string is empty.  It uses
    :class:`difflib.SequenceMatcher` which is part of the Python standard
    library and therefore available without additional dependencies.
    """

    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def cluster_topics(session: Session, threshold: float = 0.3) -> None:
    """Cluster recent messages into topics.

    Messages from the last 24 hours that are not yet associated with a topic
    are grouped using a very small similarity heuristic.  Each resulting group
    becomes a new :class:`Topic` instance with corresponding
    :class:`TopicMessage` links.
    """

    cutoff = datetime.utcnow() - timedelta(hours=24)
    messages = session.scalars(
        select(Message)
        .where(Message.date >= cutoff)
        .where(~Message.topic_messages.any())
    ).all()

    clusters: list[list[Message]] = []
    for msg in messages:
        placed = False
        for cluster in clusters:
            if _similarity(msg.text, cluster[0].text) >= threshold:
                cluster.append(msg)
                placed = True
                break
        if not placed:
            clusters.append([msg])

    for cluster in clusters:
        if not cluster:
            continue
        title = (cluster[0].text or "")[:255]
        topic = Topic(title=title)
        session.add(topic)
        session.flush()  # obtain topic.id
        for msg in cluster:
            session.add(TopicMessage(topic_id=topic.id, message_id=msg.id))
    session.commit()
    if clusters:
        logger.info("clustered %s topic groups", len(clusters))


# ---------------------------------------------------------------------------
# Ranking computation
# ---------------------------------------------------------------------------

def _popularity(msg: Message) -> int:
    return (
        (msg.views or 0)
        + (msg.reactions or 0)
        + (msg.forwards or 0)
        + (msg.comments or 0)
    )


def compute_ranking(session: Session) -> None:
    """Compute ranking scores for messages and topics.

    The score is a combination of a ``popularity`` metric (views, reactions,
    forwards and comments) and a simple ``trend`` factor that favours recent
    items.  Rankings are written to the ``ranking`` table for 24 hour and 7 day
    windows.
    """

    now = datetime.utcnow()
    windows: dict[str, datetime] = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
    }

    for window_name, start in windows.items():
        msgs = session.scalars(select(Message).where(Message.date >= start)).all()
        for msg in msgs:
            popularity = _popularity(msg)
            age_hours = (now - msg.date).total_seconds() / 3600
            trend = 1 / (1 + age_hours)
            score = float(popularity) * trend

            pk = ("message", msg.id, window_name)
            ranking = session.get(Ranking, pk)
            if ranking:
                ranking.score = score
                ranking.indexed = now
            else:
                ranking = Ranking(
                    entity_kind="message",
                    entity_id=msg.id,
                    window=window_name,
                    score=score,
                    indexed=now,
                )
                session.add(ranking)

        topics = session.scalars(select(Topic)).all()
        for topic in topics:
            topic_msgs = [tm.message for tm in topic.messages if tm.message.date >= start]
            if not topic_msgs:
                continue
            popularity = sum(_popularity(m) for m in topic_msgs)
            most_recent = max(m.date for m in topic_msgs)
            age_hours = (now - most_recent).total_seconds() / 3600
            trend = 1 / (1 + age_hours)
            score = float(popularity) * trend

            pk = ("topic", topic.id, window_name)
            ranking = session.get(Ranking, pk)
            if ranking:
                ranking.score = score
                ranking.indexed = now
            else:
                ranking = Ranking(
                    entity_kind="topic",
                    entity_id=topic.id,
                    window=window_name,
                    score=score,
                    indexed=now,
                )
                session.add(ranking)
    session.commit()


# ---------------------------------------------------------------------------
# Periodic scheduling
# ---------------------------------------------------------------------------

async def schedule_jobs(
    session_factory: sessionmaker,
    *,
    topic_interval: int = 3600,
    ranking_interval: int = 600,
) -> None:
    """Start background tasks for clustering topics and computing rankings.

    Parameters
    ----------
    session_factory:
        Factory returning new :class:`~sqlalchemy.orm.Session` instances.  It is
        typically the ``sessionmaker`` configured for the application's
        database.
    topic_interval:
        Number of seconds between successive invocations of
        :func:`cluster_topics`.
    ranking_interval:
        Number of seconds between successive invocations of
        :func:`compute_ranking`.
    """

    async def _periodic(func: Callable[[Session], None], interval: int) -> None:
        while True:  # pragma: no branch - simple loop
            with session_factory() as session:
                func(session)
            await asyncio.sleep(interval)

    await asyncio.gather(
        _periodic(cluster_topics, topic_interval),
        _periodic(compute_ranking, ranking_interval),
    )


__all__ = ["cluster_topics", "compute_ranking", "schedule_jobs"]
