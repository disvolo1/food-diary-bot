import json
import os
import re

from google import genai
from google.genai import types


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


client = genai.Client(
    api_key=GEMINI_API_KEY
)


MODEL_NAME = "gemini-2.5-flash-lite"


PROMPT = """
Ты — система распознавания пищевой ценности продуктов.

Пользователь отправил фотографию упаковки продукта.
На фотографии может быть таблица пищевой ценности.

ТВОЯ ЗАДАЧА:

Внимательно изучи ВСЮ фотографию и найди информацию о пищевой ценности.

Особенно ищи:

- Energy / Энергетическая ценность
- kcal / ккал
- kJ / кДж
- Protein / Белки
- Fat / Жиры
- Carbohydrate / Углеводы
- Carbs
- Eiweiß
- Fett
- Kohlenhydrate

Фотография может быть на русском, английском или немецком языке.

ОБЯЗАТЕЛЬНО:

1. Сначала визуально найди таблицу пищевой ценности.
2. Определи, указаны ли значения на 100 г, 100 мл,
   порцию или всю упаковку.
3. Если на упаковке есть значения одновременно
   "на 100 г" и "на порцию", используй "на 100 г".
4. Для напитков, если таблица указана на 100 мл,
   используй 100 мл.
5. Калории бери именно из kcal / ккал.
6. НЕ используй kJ вместо kcal.
7. Белок бери из Protein / Белки / Eiweiß.
8. Жиры бери из Fat / Жиры / Fett.
9. Углеводы бери из Carbohydrate / Углеводы /
   Kohlenhydrate.
10. Не используй сахара вместо углеводов.
11. Не используй насыщенные жиры вместо общего количества жиров.
12. Не придумывай отсутствующие значения.
13. Если конкретное значение невозможно прочитать,
    поставь null.
14. Очень внимательно проверяй цифры.
15. Если фотография немного наклонена или текст небольшой,
    всё равно попытайся распознать его.
16. Если таблица находится сбоку или вертикально,
    тоже попытайся её прочитать.

ВАЖНО:

Если на фотографии есть несколько чисел,
не выбирай первое попавшееся число.

Нужно определить именно:

КАЛОРИИ
БЕЛКИ
ЖИРЫ
УГЛЕВОДЫ

Например, если таблица выглядит примерно так:

Nährwerte
pro 100 g

Energie 850 kJ / 200 kcal
Fett 10 g
davon gesättigte Fettsäuren 2 g
Kohlenhydrate 20 g
davon Zucker 5 g
Eiweiß 15 g

результат должен быть:

calories = 200
protein = 15
fat = 10
carbs = 20

Не используй 850 вместо 200.
Не используй 2 вместо 10.
Не используй 5 вместо 20.

НАЗВАНИЕ:

Попробуй определить название продукта с упаковки.
Если определить невозможно, используй:
"Неизвестный продукт"

ОСНОВА:

Если значения указаны:

на 100 г → "100g"
на 100 мл → "100ml"
на порцию → "portion"
на упаковку → "package"

Если определить невозможно → null.

ОТВЕТ:

Верни ТОЛЬКО валидный JSON.

Строго используй этот формат:

{
  "name": "Название продукта",
  "calories": 200,
  "protein": 15,
  "fat": 10,
  "carbs": 20,
  "basis": "100g"
}

Числа должны быть числами, а не строками.

Если значение неизвестно:

{
  "name": "Название продукта",
  "calories": null,
  "protein": null,
  "fat": null,
  "carbs": null,
  "basis": null
}

Не добавляй markdown.
Не добавляй ```json.
Не добавляй объяснение.
Только JSON.
"""


def extract_json(text: str):

    text = text.strip()

    # Если Gemini всё-таки обернул JSON в markdown
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Пытаемся найти JSON внутри ответа
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            f"Gemini did not return JSON. Response: {text}"
        )

    try:
        return json.loads(
            match.group(0)
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            f"Invalid JSON from Gemini: {text}"
        ) from error


async def analyze_food_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg"
):

    if not image_bytes:
        raise ValueError(
            "Empty image"
        )

    response = await client.aio.models.generate_content(

        model=MODEL_NAME,

        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            ),
            PROMPT
        ],

        config=types.GenerateContentConfig(

            temperature=0,

            response_mime_type="application/json"
        )
    )

    if not response.text:

        raise ValueError(
            "Gemini returned an empty response"
        )

    print(
        "GEMINI RAW RESPONSE:",
        response.text
    )

    data = extract_json(
        response.text
    )

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
                f"Gemini response is missing: {field}"
            )

    return data
