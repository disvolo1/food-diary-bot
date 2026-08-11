````python
import json
import os
import re

from google import genai
from google.genai import types


# ============================================================
# CONFIG
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


MODEL_NAME = "gemini-3.1-flash-lite"


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# PROMPT
# ============================================================

PROMPT = """
Ты — помощник для дневника питания.

Пользователь отправляет фотографию упаковки продукта питания.
На фотографии находится этикетка или таблица пищевой ценности.

Твоя задача — внимательно прочитать фотографию и определить:

- название продукта;
- калории;
- белки;
- жиры;
- углеводы;
- основу, на которую указаны значения.


========================
ЯЗЫКИ
========================

Учитывай русский, английский и немецкий языки.

Русский:
Энергетическая ценность
ккал
кДж
Белки
Жиры
Углеводы

Английский:
Energy
kcal
kJ
Protein
Fat
Carbohydrate
Carbs

Немецкий:
Energie
Eiweiß
Fett
Kohlenhydrate


========================
ОСНОВНЫЕ ПРАВИЛА
========================

1. Не придумывай значения.

2. Если значение невозможно прочитать,
используй null.

3. Если на упаковке есть значения одновременно
на 100 г и на порцию,
используй значения на 100 г.

4. Для напитков используй значения на 100 мл,
если именно так указана таблица.

5. Если одновременно указаны kJ и kcal,
используй kcal.

Например:

850 kJ / 200 kcal

означает:

calories = 200


========================
БЕЛКИ
========================

Используй только:

Protein
Белки
Eiweiß


========================
ЖИРЫ
========================

Используй общий показатель:

Fat
Жиры
Fett

Например:

Fat 10 g
Saturates 2 g

нужно:

fat = 10

НЕ используй насыщенные жиры.


========================
УГЛЕВОДЫ
========================

Используй общий показатель:

Carbohydrate
Carbs
Углеводы
Kohlenhydrate

Например:

Carbohydrate 20 g
Sugars 5 g

нужно:

carbs = 20

НЕ используй сахара.


========================
ДЕСЯТИЧНЫЕ ЗНАЧЕНИЯ
========================

Сохраняй десятичные значения.

Например:

12,5 g

должно стать:

12.5


========================
ПЛОХОЕ ФОТО
========================

Если фотография:

- немного наклонена;
- имеет блики;
- сделана под углом;
- текст находится сбоку;
- таблица расположена вертикально;
- упаковка немного помята;

всё равно попытайся прочитать данные.

Но не придумывай значения.


========================
BASIS
========================

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


========================
НАЗВАНИЕ
========================

Попробуй определить название продукта.

Если определить невозможно:

"Неизвестный продукт"


========================
ФОРМАТ
========================

Верни ТОЛЬКО JSON.

Строго такой формат:

{
  "name": "Название продукта",
  "calories": 200,
  "protein": 15,
  "fat": 10,
  "carbs": 20,
  "basis": "100g"
}

Числовые значения должны быть числами,
а не строками.

Если значение невозможно определить:

{
  "name": "Неизвестный продукт",
  "calories": null,
  "protein": null,
  "fat": null,
  "carbs": null,
  "basis": null
}

НЕ добавляй:

- markdown;
- ```json;
- комментарии;
- объяснения;
- дополнительный текст.

ТОЛЬКО JSON.
"""


# ============================================================
# JSON PARSER
# ============================================================

def extract_json(text: str):

    if not text:
        raise ValueError(
            "Gemini returned an empty response"
        )

    text = text.strip()

    # Убираем markdown-обёртку
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

    # Пробуем распарсить ответ целиком
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Если Gemini добавил текст вокруг JSON
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            f"Gemini did not return valid JSON: {text}"
        )

    json_text = match.group(0)

    try:
        return json.loads(json_text)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON from Gemini: {json_text}"
        ) from error


# ============================================================
# ANALYZE FOOD IMAGE
# ============================================================

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


    # ========================================================
    # PARSE JSON
    # ========================================================

    data = extract_json(
        response.text
    )


    # ========================================================
    # REQUIRED FIELDS
    # ========================================================

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


    # ========================================================
    # NUMERIC VALUES
    # ========================================================

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

            print(
                f"Could not convert {field}: {value}"
            )

            data[field] = None


    # ========================================================
    # BASIS
    # ========================================================

    allowed_basis = {
        "100g",
        "100ml",
        "portion",
        "package"
    }

    if data.get("basis") not in allowed_basis:

        data["basis"] = None


    # ========================================================
    # NAME
    # ========================================================

    if not data.get("name"):

        data["name"] = "Неизвестный продукт"

    else:

        data["name"] = str(
            data["name"]
        ).strip()


    # ========================================================
    # FINAL RESULT
    # ========================================================

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
