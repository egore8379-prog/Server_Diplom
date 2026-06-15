# Структура файлу:
# 1. Імпорти та налаштування
# 2. Моделі даних (що ми отримуємо і що віддаємо)
# 3. Допоміжні функції (очистка цін, тексту)
# 4. Методи пошуку (JSON-LD та HTML селектори)
# 5. API Маршрути (отримання запитів)

# 1. ІМПОРТИ ТА НАЛАШТУВАННЯ
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from curl_cffi import requests
import json
import re

app = FastAPI()

# Дозволяємо запити з будь-якого джерела (для Android, Web, тощо)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Заголовки, щоб сайти думали, що це звичайний браузер
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"
}

# 2. МОДЕЛІ ДАНИХ
class ParseRequest(BaseModel):
    url: str  # Тільки посилання

class ParseResponse(BaseModel):
    name: str              # Назва товару
    currentPrice: str      # Ціна як текст (напр. "1 200 UAH")

# 3. ДОПОМІЖНІ ФУНКЦІЇ
def clean_price(text):
    """Очищає текст ціни, залишаючи тільки число (1 200 грн -> 1200.0)"""
    if not text:
        return 0.0
    
    # Видаляємо пробіли та міняємо кому на крапку
    text = str(text).replace(" ", "").replace("\xa0", "").replace(",", ".")
    
    # Шукаємо число в тексті
    match = re.search(r"(\d+(\.\d+)?)", text)
    if match:
        return float(match.group(1))
    
    return 0.0

def format_price(price, currency="UAH"):
    """Форматує число назад в красивий текст (1200.0 -> 1200 UAH)"""
    if price == 0:
        return "0"
    return f"{int(price)} {currency}"

# 4. МЕТОДИ ПОШУКУ (ЛОГІКА ПАРСИНГУ)
def find_json_ld(soup):
    """МЕТОД 1: Шукає прихований JSON з даними про товар (найточніший метод)"""
    scripts = soup.find_all("script", {"type": "application/ld+json"})

    for script in scripts:
        try:
            data = json.loads(script.string)

            # Іноді JSON це список, шукаємо потрібний елемент
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Product":
                        data = item
                        break

            # Перевіряємо чи це Продукт
            if data.get("@type") == "Product":
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]

                price = clean_price(offers.get("price"))

                if price > 0:
                    return {
                        "name": data.get("name", "Невідома назва"),
                        "currentPrice": format_price(price, offers.get("priceCurrency", "UAH"))
                    }
        except:
            continue

    return None


def find_by_selectors(soup):
    """МЕТОД 2: Шукає дані через звичайні HTML теги (запасний варіант)"""
    
    # 1. Шукаємо Ціну
    price_element = soup.select_one("[itemprop='price']")
    if not price_element:
        price_element = soup.find("meta", property="product:price:amount")
    
    if not price_element:
        return None
    
    # 2. Шукаємо Назву
    name_element = soup.select_one("h1")
    if not name_element:
        name_element = soup.find("meta", property="og:title")
    
    # 3. Витягуємо Текст
    price_value = price_element.get("content") or price_element.get_text()
    
    name_value = "Невідома назва"
    if name_element:
        name_value = name_element.get("content") or name_element.get_text()
    
    # 4. Формуємо результат
    price = clean_price(price_value)
    
    if price > 0:
        return {
            "name": name_value.strip(),
            "currentPrice": format_price(price)
        }
    
    return None


# 5. API МАРШРУТИ
@app.post("/parse", response_model=ParseResponse)
def parse_product(request: ParseRequest):
    """Головний вхід: приймає посилання, повертає інфо про товар"""
    print(f"Аналізую: {request.url}")

    try:
        # 1. Завантажуємо сторінку
        page = requests.get(request.url, headers=HEADERS, impersonate="safari15_5", timeout=15)
        page.encoding = "utf-8"
        
        if page.status_code == 200:
            soup = BeautifulSoup(page.text, "html.parser")
            
            # 2. Пробуємо знайти МЕТОДОМ 1 (JSON)
            product = find_json_ld(soup)
            
            # 3. Якщо не вийшло - пробуємо МЕТОДОМ 2 (HTML)
            if not product:
                product = find_by_selectors(soup)
            
            # 4. Повертаємо результат
            if product:
                print(f"Успіх: {product['name']} | Ціна: {product['currentPrice']}")
                return ParseResponse(
                    name=product["name"],
                    currentPrice=product["currentPrice"]
                )

    except Exception as error:
        print(f"Помилка: {error}")

    # Якщо нічого не знайшли
    print("Не знайдено")
    return ParseResponse(name="Не знайдено", currentPrice="0")


@app.get("/")
def root():
    """Перевірка що сервер працює"""
    return {"status": "OK", "message": "PriceTracker Server is running"}
