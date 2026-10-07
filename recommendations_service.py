import logging
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
import pandas as pd
import httpx

logger = logging.getLogger("uvicorn.error")
events_store_url = "http://localhost:8010"
features_store_url = "http://localhost:8020"

class Recommendations:

    def __init__(self):

        self._recs = {"personal": None, "default": None}
        self._stats = {
            "request_personal_count": 0,
            "request_default_count": 0,
        }

    def load(self, type, path, **kwargs):
        """
        Загружает рекомендации из файла
        """
        logger.info(f"Loading recommendations")
        try:
            df = pd.read_parquet(path, **kwargs)
            if type == "personal":
                self._recs[type] = df.set_index("user_id")
            elif type == "default":
                self._recs[type] = df["item_id"].drop_duplicates().tolist()
        except FileNotFoundError:
            logger.critical(f"File not found: {path}")
            raise
        except Exception as e:
            logger.exception(f"Failed to load recommendations from {path}: {e}")
            raise
        logger.info(f"Loaded")

    def get(self, user_id: int, k: int=100):
        """
        Возвращает список рекомендаций для пользователя
        """
        try:
            recs = self._recs["personal"].loc[user_id]
            recs = recs["item_id"].to_list()[:k]
            self._stats["request_personal_count"] += 1
        except KeyError:
            recs = self._recs["default"][:k]
            self._stats["request_default_count"] += 1
        except:
            logger.error("No recommendations found")
            recs = []

        return recs

    def stats(self):

        logger.info("Stats for recommendations")
        for name, value in self._stats.items():
            logger.info(f"{name:<30} {value} ")

rec_store = Recommendations()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting")
    rec_store.load(
        "personal",
        "recommendations/recommendations.parquet",
        columns=["user_id", "item_id", "cb_score", "rank"],
    )
    rec_store.load(
        "default",
        "recommendations/top_popular.parquet",
        columns=["user_id", "item_id", "rank"],
    )

    async with httpx.AsyncClient(timeout=5.0) as client:
        app.state.http_client = client
        yield
    # этот код выполнится только один раз при остановке сервиса
    logger.info("Stopping")
    
# создаём приложение FastAPI
app = FastAPI(title="recommendations", lifespan=lifespan)

@app.post("/recommendations_offline")
async def recommendations_offline(user_id: int, k: int = 100):
    """
    Возвращает список рекомендаций длиной k для пользователя user_id
    """
    recs = rec_store.get(user_id, k)

    return {"rec": recs}


@app.post("/recommendations_online")
async def recommendations_online(user_id: int, k: int = 100):
    """
    Возвращает список онлайн-рекомендаций длиной k для пользователя user_id
    """

    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    params = {"user_id": user_id, "k": 3}
    client = app.state.http_client 
    resp = await client.post(events_store_url + "/get", params=params, headers=headers)
    resp.raise_for_status()
    history_items = resp.json()["events"][:3]
    if not history_items:
        return {"rec": []}
    tasks = [client.post(features_store_url + "/similar_items", 
                            headers=headers,
                            params={ "item_id": item, "k": k, }) for item in history_items]
    responses = await asyncio.gather(*tasks)

    weights = [0.50, 0.33, 0.17]
    recs = []
    candidate_scores = {}
    seen = set(history_items)
    for weight, response in zip(weights, responses):
        response.raise_for_status()
        data = response.json()
        sim_items = data['items_id']
        scores = data['score']
        for candidate_id, score in zip(sim_items, scores):
            if candidate_id in seen:
                continue
            candidate_scores[candidate_id] = candidate_scores.get(candidate_id, 0) + weight * score
    ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
    recs = [i[0] for i in ranked[:k]]
    return {"rec": recs}

def interleave_recommendations(online, offline, k, online_ratio=0.7):
    result = []
    seen = set()

    online_count = 0
    offline_count = 0

    target_online = round(k * online_ratio)
    target_offline = k - target_online

    i = 0
    j = 0

    while len(result) < k:
        # Пока не набрали квоту online
        if online_count < target_online and i < len(online):
            item = online[i]
            i += 1
            if item not in seen:
                result.append(item)
                seen.add(item)
                online_count += 1
                continue

        # Пока не набрали квоту offline
        if offline_count < target_offline and j < len(offline):
            item = offline[j]
            j += 1

            if item not in seen:
                result.append(item)
                seen.add(item)
                offline_count += 1
                continue

        # Если один источник закончился — добираем из другого
        if i >= len(online) and j < len(offline):
            item = offline[j]
            j += 1
            if item not in seen:
                result.append(item)
                seen.add(item)

        elif j >= len(offline) and i < len(online):
            item = online[i]
            i += 1
            if item not in seen:
                result.append(item)
                seen.add(item)

        else:
            break

    return result[:k]

@app.post("/recommendations")
async def recommendations(user_id: int, k: int = 100):
    rec_online, rec_offline = await asyncio.gather(recommendations_online(user_id=user_id, k=k),
                                                   recommendations_offline(user_id=user_id, k=k))

    rec_online = rec_online['rec']
    rec_offline = rec_offline['rec']
    # будет брать рекомменадции в пропорции 70/30 для онлайн и оффлайн рекоменадции соответственно
    recs = interleave_recommendations(online=rec_online, offline=rec_offline, k=k)
    return {"rec": recs}

    