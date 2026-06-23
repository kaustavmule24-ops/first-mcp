from fastapi import FastAPI, Request
import httpx
import asyncio
from datetime import datetime
import pytz
import logging
import json
import os

app = FastAPI()

# ==============================
# 🪵 LOGGING CONFIG
# ==============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("MCP_SERVER")

# Shared async client (IMPORTANT for performance)
client = httpx.AsyncClient(timeout=10)


# ==============================
# 🔧 SAFE ASYNC REQUEST HELPERS
# ==============================

async def safe_get_json(url):
    logger.info(f"➡️ GET JSON: {url}")

    try:
        res = await client.get(url)

        logger.info(f"⬅️ Status: {res.status_code}")

        if res.status_code != 200:
            logger.error(f"❌ Bad status: {res.status_code}")
            return None

        if not res.text.strip():
            logger.error("❌ Empty response")
            return None

        return res.json()

    except httpx.ReadTimeout:
        logger.error("⏳ Timeout")
        return None

    except Exception as e:
        logger.exception(f"❌ JSON Error: {e}")
        return None


async def safe_get_text(url):
    logger.info(f"➡️ GET TEXT: {url}")

    try:
        res = await client.get(url)

        logger.info(f"⬅️ Status: {res.status_code}")

        if res.status_code != 200:
            logger.error(f"❌ Text status: {res.status_code}")
            return None

        return res.text

    except httpx.ReadTimeout:
        logger.error("⏳ Text timeout")
        return None

    except Exception as e:
        logger.exception(f"❌ TEXT Error: {e}")
        return None


# ==============================
# 🌍 COORDINATES
# ==============================

async def get_coordinates(city):
    logger.info(f"🌍 Fetching coordinates: {city}")

    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    res = await safe_get_json(url)

    if not res or "results" not in res or not res["results"]:
        logger.error("❌ City not found")
        return None

    data = res["results"][0]

    return {
        "city": data.get("name"),
        "country": data.get("country"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone")
    }


# ==============================
# 🌡 WEATHER
# ==============================

async def get_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    res = await safe_get_json(url)
    return res.get("current_weather") if res else None


# ==============================
# 🌫 AQI
# ==============================

async def get_aqi(lat, lon):
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10,pm2_5,us_aqi"
    res = await safe_get_json(url)
    return res.get("current") if res else None


# ==============================
# 🕒 TIME (sync is fine)
# ==============================

def get_time(timezone):
    try:
        tz = pytz.timezone(timezone)
        return datetime.now(tz).strftime("%d %B %Y, %I:%M %p")
    except Exception as e:
        logger.exception(f"❌ Time error: {e}")
        return None


# ==============================
# 🎉 HOLIDAY
# ==============================

async def get_today_holiday(country_code="IN"):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    year = today[:4]

    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    res = await safe_get_json(url)

    if not res:
        return None

    for holiday in res:
        if holiday.get("date") == today:
            return holiday.get("localName")

    return None


# ==============================
# 📚 FACT
# ==============================

async def get_today_fact():
    today = datetime.utcnow()
    url = f"http://numbersapi.com/{today.month}/{today.day}/date"
    return await safe_get_text(url)


# ==============================
# ♻️ KEEP-ALIVE (Self-ping to prevent Render sleep)
# ==============================

SELF_URL = os.environ.get("SELF_URL", "https://mcp-weather-s1s0.onrender.com/tool")
KEEP_ALIVE_INTERVAL = 540  # 9 minutes (in seconds)

async def keep_alive_loop():
    """
    Background task that pings this server every 9 minutes
    to prevent Render.com from spinning down the free tier instance.
    """
    logger.info(f"♻️ Keep-alive started — pinging {SELF_URL} every {KEEP_ALIVE_INTERVAL // 60} minutes")
    
    # Wait a bit on first startup so the server is fully ready
    await asyncio.sleep(30)
    
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as ping_client:
                response = await ping_client.post(
                    SELF_URL,
                    json={"tool": "healthCheck"},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info("♻️ Keep-alive ping successful — server is awake")
                else:
                    logger.warning(f"♻️ Keep-alive ping returned status {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"♻️ Keep-alive ping failed: {e}")
        
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """
    Start the keep-alive background task when the server boots up.
    """
    asyncio.create_task(keep_alive_loop())
    logger.info("🚀 MCP Server startup complete — keep-alive task registered")


# ==============================
# 🧠 TOOL HANDLER
# ==============================

@app.post("/tool")
async def tool_handler(request: Request):
    try:
        payload = await request.json()

        logger.info("🔥 MCP SERVER HIT")
        logger.info(json.dumps(payload, indent=2))

        tool = payload.get("tool")
        city = payload.get("input")

        # ❤️ HEALTH CHECK
        if tool == "healthCheck":
            return {
                "status": "ok",
                "server": "MCP ASYNC RUNNING",
                "version": "V7-ASYNC"
            }

        if not city:
            return {"error": "No city provided"}

        coord = await get_coordinates(city)

        if not coord:
            return {"error": "City not found"}

        lat = coord["latitude"]
        lon = coord["longitude"]

        # 🚀 PARALLEL EXECUTION (KEY BOOST)
        weather_task = get_weather(lat, lon)
        aqi_task = get_aqi(lat, lon)
        holiday_task = get_today_holiday("IN")
        fact_task = get_today_fact()

        weather, aqi, holiday, fact = await asyncio.gather(
            weather_task,
            aqi_task,
            holiday_task,
            fact_task
        )

        result = {
            "source": "MCP_SERVER_V7_ASYNC",
            "city": coord["city"],
            "country": coord["country"],
            "latitude": lat,
            "longitude": lon
        }

        if weather:
            result["weather"] = weather

        if aqi:
            result["aqi"] = aqi

        current_time = get_time(coord["timezone"])
        if current_time:
            result["current_time"] = current_time

        special = {}
        if holiday:
            special["holiday"] = holiday
        if fact:
            special["fact"] = fact

        if special:
            result["today_special"] = special

        logger.info("✅ Final Response:")
        logger.info(json.dumps(result, indent=2))

        return result

    except Exception as e:
        logger.exception(f"💥 CRITICAL ERROR: {e}")
        return {"error": "Internal server error"}
