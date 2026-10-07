import requests


BASE_URL = "http://localhost:8000"
EVENTS_URL = "http://localhost:8010"


def add_online_history(user_id, items):

    for item_id in items:
        response = requests.post(
            f"{EVENTS_URL}/put",
            params={
                "user_id": user_id,
                "item_id": item_id,
            },
        )
        response.raise_for_status()

        print(f"Added item: {item_id}")

    print()


def get_history(user_id, k=10):
    response = requests.post(
        f"{EVENTS_URL}/get",
        params={
            "user_id": user_id,
            "k": k,
        },
    )

    response.raise_for_status()
    return response.json()["events"]


def get_recommendations(user_id, k=10):
    response = requests.post(
        f"{BASE_URL}/recommendations",
        params={
            "user_id": user_id,
            "k": k,
        },
    )

    response.raise_for_status()
    return response.json()



def user_with_history(user_id: int = 135, k: int = 5):
    print("Пользователь с историей взаимодействия")
    print("user_id:", user_id)
    online_items = [
        53404,
        33311009,
        178529,
        35505245,
        24692821,
    ]

    # Создаём онлайн-активность
    add_online_history(user_id, online_items)

    # Проверяем, что история действительно сохранилась
    history = get_history(user_id, k=5)
    print("history:", history)
    print()

    # Получаем итоговые рекомендации
    result = get_recommendations(user_id, k=k)
    print("Recommendations k=", k)
    print(result)
    return result


def user_without_history(user_id: int = 2005, k: int = 5):
    print("Персональные рекомендации для пользователя без истории взаимодействия")
    print("user_id:", user_id)
    result = get_recommendations(user_id, k=k)
    print("Recommendations k=", k)
    print(result)
    return result

def cold_user(user_id: int = 10000000, k: int = 5):
    print("Холодный пользователь")
    print("user_id:", user_id)
    result = get_recommendations(user_id=user_id, k=k)
    print("Recommendations k=", k)
    print(result)
    print()
    return result

def main():
    cold_user()
    user_without_history()
    user_with_history()

main()