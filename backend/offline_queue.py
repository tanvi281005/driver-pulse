# backend/offline_queue.py
import json
import os
from threading import Lock

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "outputs", "event_queue.json")
QUEUE_PATH = os.path.abspath(QUEUE_PATH)
_lock = Lock()

def append_event(event):
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    with _lock:
        try:
            if os.path.exists(QUEUE_PATH):
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    q = json.load(f)
            else:
                q = []
        except Exception:
            q = []
        q.append(event)
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(q, f, default=str)

def read_all():
    with _lock:
        try:
            if os.path.exists(QUEUE_PATH):
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return []
    return []

def clear():
    with _lock:
        try:
            with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass