import json
import os
import re

from google import genai
from google.genai import types


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


# ВАЖНО: здесь НЕ должно быть gemini-2.5-flash-lite
MODEL_NAME = "gemini-3.1-flash-lite"


client = genai.Client(
    api_key=GEMINI_API_KEY
)


PROMPT = """
Ты помощник для дневника питания.

На изображении находится фотография упаковки продукта
или таблицы пищевой ценности.

Тебе нужно внимательно прочитать изображение
и определить:

- название продукта;
- калории;
- белки;
- жиры;
- углеводы;
- основу, на которую указаны значения.

Поддерживаются русский, английский и немецкий языки.


ПРАВИЛА:

1. Не придумывай значения.

2. Если значение невозможно прочитать,
используй null.

3. Если есть значения одновременно на 100 г
и на порцию, используй значения на 100 г.

4. Для напитков используй значения на 100 мл,
если именно так указана таблица.

5. Если указаны kJ и kcal,
используй kcal.

Например:

850 kJ / 200 kcal

означает:

calories = 200


БЕЛКИ:

Используй только:

Protein
Белки
Eiweiß


ЖИРЫ:

Используй общий показатель:

Fat
Жиры
Fett

Если написано:

Fat 10 g
Saturates 2 g

используй:

fat = 10

Не используй насыщенные жиры.


УГЛЕВОДЫ:

Используй общий показатель:

Carbohydrate
Carbs
Углеводы
Kohlenhydrate

Если написано:

Carbohydrate 20 g
Sugars 5 g

используй:

carbs = 20

Не используй сахара.


ДЕСЯТИЧНЫЕ ЗНАЧЕНИЯ:

Сохраняй десятичные значения.

Например:

12,5 g

должно стать:

12.5


ФОТОГРАФИЯ:

Если фотография немного наклонена,
таблица находится сбоку,
текст расположен вертикально,
есть блики или упаковка помята,
всё равно попытайся прочитать информацию.

Не придумывай значения.


BASIS:

Если значения указаны на 100 г:

"100g"

Если на 100 мл:

"100ml"

Если за одну порцию:

"portion"

Если за всю упаковку:

"package"

Если определить невозможно:

null


НАЗВАНИЕ:

Попробуй определить название продукта.

Если определить невозможно:

"Неизвестный продукт"


ВЕРНИ ТОЛЬКО JSON:

{
  "name": "Название продукта",
  "calories": 200,
  "protein": 15,
  "fat": 10,
  "carbs": 20,
  "basis": "100g"
}

Если значение невозможно определить:

{
  "name": "Неизвестный продукт",
  "calories": null,
  "protein": null,
  "fat": null,
  "carbs": null,
  "basis": null
}

Не добавляй markdown.
Не добавляй объяснение.
Не добавляй ```json.

ТОЛЬКО JSON.
"""


def extract_json(text: str):

    if not text:
        raise ValueError(
            "Gemini returned an empty response"
        )

    text = text.strip()

    # На случай, если Gemini всё-таки вернул markdown
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

    if not image_bytes:
        raise ValueError(
            "Empty image"
        )

    print(
        "=================================================="
    )

    print(
        "GEMINI FOOD ANALYSIS"
    )

    print(
        f"Model: {MODEL_NAME}"
    )

    print(
        f"Image size: {len(image_bytes)} bytes"
    )

    print(
        f"MIME type: {mime_type}"
    )

    print(
        "=================================================="
    )

    try:

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
                response_mime_type="application/json"
            )
        )

    except Exception as error:

        print(
            "GEMINI API ERROR:"
        )

        print(
            repr(error)
        )

        raise


    if not response.text:

        raise ValueError(
            "Gemini returned an empty response"
        )


    print(
        "GEMINI RAW RESPONSE:"
    )

    print(
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


    numeric_fields = [
        "calories",
        "protein",
        "fat",
        "carbs"
    ]

    for field in numeric_fields:

        value = data.get(field)

        if value is None:
            continue

        try:

            data[field] = float(
                str(value).replace(",", ".")
            )

        except (
            ValueError,
            TypeError
        ):

            data[field] = None


    allowed_basis = {
        "100g",
        "100ml",
        "portion",
        "package"
    }

    if data.get("basis") not in allowed_basis:

        data["basis"] = None


    if not data.get("name"):

        data["name"] = "Неизвестный продукт"

    else:

        data["name"] = str(
            data["name"]
        ).strip()


    print(
        "GEMINI PARSED RESULT:"
    )

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
    )

    print(
        "=================================================="
    )


    return data
````
