from __future__ import annotations

from app.api.v1.endpoints.chat import serialize_sse_events, sse_event
from app.services import ChatStreamEvent


def test_sse_event_serializes_named_json_event():
    assert sse_event("delta", {"text": "hi"}) == 'event: delta\ndata: {"text": "hi"}\n\n'


def test_serialize_sse_events_preserves_stream_wire_format():
    events = iter(
        [
            ChatStreamEvent(event="delta", data={"text": "hi"}),
            ChatStreamEvent(event="complete", data={"trace_id": "trace-1"}),
        ]
    )

    assert list(serialize_sse_events(events)) == [
        'event: delta\ndata: {"text": "hi"}\n\n',
        'event: complete\ndata: {"trace_id": "trace-1"}\n\n',
    ]
