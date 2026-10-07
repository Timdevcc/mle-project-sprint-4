from fastapi import FastAPI
from collections import deque

class EventStore:

    def __init__(self, max_events_per_user=10):

        self.events: dict[int, deque] = {}
        self.max_events_per_user = max_events_per_user

    def put(self, user_id, item_id):
        """
        Сохраняет событие
        """

        if user_id not in self.events:
            self.events[user_id] = deque(maxlen=self.max_events_per_user)
        self.events[user_id].appendleft(item_id)

    def get(self, user_id, k):
        """
        Возвращает события для пользователя
        """
        user_events = self.events.get(user_id, deque(maxlen=self.max_events_per_user))

        return list(user_events)[:k]

events_store = EventStore()

# создаём приложение FastAPI
app = FastAPI(title="events")

@app.post("/put")
async def put(user_id: int, item_id: int):
    """
    Сохраняет событие для user_id, item_id
    """

    events_store.put(user_id, item_id)

    return {"result": "ok"}

@app.post("/get")
async def get(user_id: int, k: int = 10):
    """
    Возвращает список последних k событий для пользователя user_id
    """

    events = events_store.get(user_id, k)

    return {"events": events}