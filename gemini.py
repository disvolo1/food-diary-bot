import json
import os
import re

from google import genai
from google.genai import types


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


client = genai.Client(api_key=GEMINI_API_KEY)


MODEL_NAME = "gemini-2.5-flash-lite"


PROMPT = """
Ты помощник для приложения дневника питания.

На изображении находится этикетка продукта питания.

Твоя задача — внимательно прочитать этикетку и определить пищевую ценность.

Нужно найти:

1. Название продукта
2. Калории
3. Белки
4. Жиры
5. Углеводы
6. На какое количество указаны значения:
   - на 100 г
   - на 100 мл
   - на порцию
   - на упаковку

Очень важно:

- Не придумывай значения, которых нет на изображении.
- Если какое-либо значение невозможно прочитать, поставь null.
- Если на этикетке указаны и значения на 100 г, и на порцию, используй значения на 100 г.
- Если продукт жидкий, используй 100 мл.
- Калории должны быть числом.
- Белки, жиры и углеводы должны быть числами.
- Не учитывай сахар отдельно от углеводов.
- Не путай жиры и насыщенные жиры.
- Не путай углеводы и сахара.
- Если на этикетке указана энергетическая ценность одновременно в kJ и kcal, используй kcal.

Верни ТОЛЬКО JSON без markdown и без пояснений.

Формат:

{
  "name": "Название продукта",
  "calories": 0,
  "protein": 0,
  "fat": 0,
  "carbs": 0,
  "basis": "100g"
}

Поле basis может быть только:

"100g"
"100ml"
"portion"
"package"

Если определить основу невозможно, используй null.
"""


def extract_json(text: str):
    """
    Иногда модель может добавить лишний текст вокруг JSON.
    Эта функция пытается найти JSON внутри ответа.
    """

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("Gemini did not return valid JSON")

    return json.loads(match.group(0))


async def analyze_food_image(image_bytes: bytes):
    """
    Отправляет фотографию этикетки в Gemini
    и возвращает распознанные КБЖУ.
    """

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            ),
            PROMPT
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json"
        )
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response")

    data = extract_json(response.text)

    required_fields = [
        "name",
        "calories",
        "protein",
        "fat",
        "carbs",
        "basis"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(
                f"Gemini response is missing field: {field}"
            )

    return data
