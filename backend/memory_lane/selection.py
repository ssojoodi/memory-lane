import json
import random
from datetime import datetime, timedelta, timezone


RESURFACE_CHANCE = 0.2
RESURFACE_COOLDOWN_DAYS = 7
RANDOM_POOL_SIZE = 50
QUERY_LIMIT = 200


def _cutoff(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace(
        "+00:00", "Z"
    )


def _candidates(
    connection,
    *,
    annotated=None,
    shown_before=None,
    include_skipped=False,
    annotated_order=False,
):
    joins = "JOIN reflections f ON f.photo_id=p.id" if annotated is True else ""
    conditions = ["r.enabled=1", "p.available=1", "p.hidden_at IS NULL"]
    parameters = []

    if annotated is False:
        conditions.append(
            "NOT EXISTS(SELECT 1 FROM reflections f WHERE f.photo_id=p.id)"
        )
    if shown_before:
        conditions.append("(p.last_shown_at IS NULL OR p.last_shown_at < ?)")
        parameters.append(shown_before)
    if not include_skipped:
        conditions.append(
            "NOT EXISTS(SELECT 1 FROM events e WHERE e.photo_id=p.id "
            "AND e.kind='skipped' "
            "AND date(e.occurred_at,'localtime')=date('now','localtime'))"
        )

    order = (
        "COALESCE(p.last_shown_at,f.updated_at),p.id"
        if annotated_order
        else "CASE WHEN p.last_shown_at IS NULL THEN 0 ELSE 1 END,p.last_shown_at,p.id"
    )
    query = f"""SELECT p.* FROM photos p
        JOIN library_roots r ON r.id=p.root_id
        {joins}
        WHERE {' AND '.join(conditions)}
        ORDER BY {order}
        LIMIT {QUERY_LIMIT}"""
    return connection.execute(query, parameters).fetchall()


def select_next_photo(connection):
    setting = connection.execute(
        "SELECT value_json FROM settings WHERE key='cooldownDays'"
    ).fetchone()
    fresh_cooldown = int(json.loads(setting[0])) if setting else 90

    fresh = _candidates(
        connection,
        annotated=False,
        shown_before=_cutoff(fresh_cooldown),
    )
    annotated = _candidates(
        connection,
        annotated=True,
        shown_before=_cutoff(RESURFACE_COOLDOWN_DAYS),
        annotated_order=True,
    )

    if annotated and (not fresh or random.random() < RESURFACE_CHANCE):
        pool = annotated
    else:
        pool = fresh

    if not pool:
        pool = _candidates(connection)
    if not pool:
        pool = _candidates(connection, include_skipped=True)
    if not pool:
        return None
    return random.choice(pool[:RANDOM_POOL_SIZE])
