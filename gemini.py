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
Ты помощник для дневника питания.

На изображении находится этикетка продукта питания.

Тебе нужно внимательно прочитать таблицу пищевой ценности и вернуть данные
для дальнейшего автоматического расчёта.

Найди:

- название продукта;
- калории;
- белки;
- жиры;
- углеводы;
- основу, на которую указаны значения.

ОСОБЕННО ВАЖНО:

1. Не придумывай значения.
2. Если значение невозможно прочитать, используй null.
3. Если есть значения одновременно на 100 г и на порцию,
   используй значения на 100 г.
4. Для напитков используй значения на 100 мл.
5. Не используй сахара вместо углеводов.
6. Не используй насыщенные жиры вместо общих жиров.
7. Если указаны kJ и kcal, используй kcal.
8. Сохраняй десятичные значения.
9. Внимательно различай цифры на фотографии.

Верни ТОЛЬКО JSON.

Формат:

{
  "name": "Название продукта",
  "calories": 0,
  "protein": 0,
  "fat": 0,
  "carbs": 0,
  "basis": "100g"
}

basis может иметь только одно из значений:

"100g"
"100ml"
"portion"
"package"

Если основу определить невозможно, верни null.

Если название продукта невозможно прочитать, используй:

"Неизвестный продукт"
"""


def extract_json(text: str):

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            "Gemini did not return valid JSON"
        )

    return json.loads(
        match.group(0)
    )


async def analyze_food_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg"
):
    """
    Отправляет фотографию этикетки в Gemini
    и получает структурированные данные КБЖУ.
    """

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
