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


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# Стабильная модель Gemini 3.1 Flash-Lite
# Поддерживает изображения и structured JSON output.
MODEL_NAME = "gemini-3.1-flash-lite"


# ============================================================
# PROMPT
# ============================================================

PROMPT = """
Ты — система распознавания пищевой ценности продуктов.

Пользователь отправил фотографию упаковки продукта питания.

На фотографии может находиться таблица пищевой ценности.
Тебе необходимо внимательно изучить всю фотографию и извлечь:

- название продукта;
- калории;
- белки;
- жиры;
- углеводы;
- основу, на которую указаны значения.


ПОДДЕРЖИВАЕМЫЕ ЯЗЫКИ:

Русский:
- Энергетическая ценность
- ккал
- кДж
- Белки
- Жиры
- Углеводы

Английский:
- Energy
- kcal
- kJ
- Protein
- Fat
- Carbohydrate
- Carbs

Немецкий:
- Energie
- Eiweiß
- Fett
- Kohlenhydrate


============================================================
ПРАВИЛА РАСПОЗНАВАНИЯ
============================================================

1. Сначала найди на фотографии таблицу пищевой ценности.

2. Определи, указаны ли значения на:
- 100 г;
- 100 мл;
- порцию;
- упаковку.

3. Если одновременно есть значения на 100 г и на порцию,
используй значения на 100 г.

4. Для напитков, если значения указаны на 100 мл,
используй 100 мл.

5. Если указаны kJ и kcal, используй только kcal.


============================================================
КАЛОРИИ
============================================================

Например:

Energy 850 kJ / 200 kcal

Результат:

calories = 200

НЕ используй 850.


============================================================
БЕЛКИ
============================================================

Используй:

Protein
Белки
Eiweiß

Не используй другие показатели.


============================================================
ЖИРЫ
============================================================

Используй:

Fat
Жиры
Fett

Например:

Fat 10 g
of which saturates 2 g

Результат:

fat = 10

НЕ используй 2.


============================================================
УГЛЕВОДЫ
============================================================

Используй:

Carbohydrate
Carbs
Углеводы
Kohlenhydrate

Например:

Carbohydrate 20 g
of which sugars 5 g

Результат:

carbs = 20

НЕ используй 5.


============================================================
ТОЧНОСТЬ
============================================================

Не придумывай значения.

Если конкретное значение невозможно прочитать,
используй null.

Очень внимательно различай цифры:

1 / 7
3 / 8
5 / 6
0 / 8

Сохраняй десятичные значения.

Например:

12,5 g

должно стать:

12.5


============================================================
ПОВЁРНУТАЯ ТАБЛИЦА
============================================================

Если таблица находится сбоку, вертикально или под углом,
всё равно попытайся её прочитать.


============================================================
НАЗВАНИЕ
============================================================

Попробуй определить название продукта.

Если определить невозможно:

"Неизвестный продукт"


============================================================
BASIS
============================================================

Если значения на 100 грамм:

"100g"

Если на 100 миллилитров:

"100ml"

Если за одну порцию:

"portion"

Если за всю упаковку:

"package"

Если определить невозможно:

null


============================================================
ПРИМЕР
============================================================

Если написано:

Nährwerte pro 100 g

Energie 850 kJ / 200 kcal
Fett 10 g
davon gesättigte Fettsäuren 2 g
Kohlenhydrate 20 g
davon Zucker 5 g
Eiweiß 15 g

верни:

{
  "name": "Название продукта",
  "calories": 200,
  "protein": 15,
  "fat": 10,
  "carbs": 20,
  "basis": "100g"
}


============================================================
ФОРМАТ ОТВЕТА
============================================================

Верни только JSON.

Строго:

{
  "name": "Название продукта",
  "calories": 200,
  "protein": 15,
  "fat": 10,
  "carbs": 20,
  "basis": "100g"
}

Числа должны быть числами, а не строками.

Если значение невозможно определить:

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

    # Убираем markdown, если модель его добавила
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

    # Пытаемся распарсить весь ответ
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Если модель добавила текст вокруг JSON
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            f"Gemini did not return valid JSON: {text}"
        )

    try:
        return json.loads(
            match.group(0)
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON from Gemini: {text}"
        ) from error


# ============================================================
# ANALYZE IMAGE
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
        f"Sending image to Gemini: "
        f"{len(image_bytes)} bytes"
    )

    print(
        f"MIME type: {mime_type}"
    )

    print(
        f"Gemini model: {MODEL_NAME}"
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
            f"Gemini API error: {error}"
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
    # NUMBERS
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
                f"Invalid value for {field}: {value}"
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

    if data["basis"] not in allowed_basis:

        data["basis"] = None


    # ========================================================
    # NAME
    # ========================================================

    if not data.get("name"):

        data["name"] = "Неизвестный продукт"

    data["name"] = str(
        data["name"]
    ).strip()


    # ========================================================
    # FINAL LOG
    # ========================================================

    print(
        "GEMINI PARSED RESULT:"
    )

    print(
        data
    )


    return data
````
