from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWKClient
import httpx
import asyncio
from datetime import datetime
import pytz
import logging
import json
import os
import urllib.parse
import unicodedata

app = FastAPI()

# ==============================
# CORS (allow frontend calls)
# ==============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# LOGGING CONFIG
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("MCP_SERVER")

# ==============================
# GATEWAY SECRET
# ==============================
GATEWAY_SECRET = os.environ.get("GATEWAY_SECRET", "")

CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "...")
CLERK_ISSUER = os.environ.get("CLERK_ISSUER", "...")
jwks_client = PyJWKClient(CLERK_JWKS_URL)

# Shared async client (IMPORTANT for performance)
client = httpx.AsyncClient(timeout=15)

# ==============================
# COUNTRY CODE MAPPING (Worldwide)
# ==============================
COUNTRY_TO_CODE = {
    "united states": "US", "usa": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
    "india": "IN", "china": "CN", "japan": "JP", "germany": "DE",
    "france": "FR", "italy": "IT", "spain": "ES", "brazil": "BR",
    "canada": "CA", "australia": "AU", "russia": "RU", "south korea": "KR",
    "korea": "KR", "mexico": "MX", "indonesia": "ID", "turkey": "TR",
    "saudi arabia": "SA", "south africa": "ZA", "argentina": "AR",
    "netherlands": "NL", "switzerland": "CH", "sweden": "SE", "belgium": "BE",
    "poland": "PL", "thailand": "TH", "iran": "IR", "nigeria": "NG",
    "egypt": "EG", "pakistan": "PK", "bangladesh": "BD", "vietnam": "VN",
    "philippines": "PH", "ethiopia": "ET", "democratic republic of the congo": "CD",
    "myanmar": "MM", "tanzania": "TZ", "kenya": "KE", "uganda": "UG",
    "algeria": "DZ", "sudan": "SD", "morocco": "MA", "angola": "AO",
    "ghana": "GH", "mozambique": "MZ", "madagascar": "MG", "cameroon": "CM",
    "cote d'ivoire": "CI", "niger": "NE", "sri lanka": "LK", "burkina faso": "BF",
    "mali": "ML", "malawi": "MW", "zambia": "ZM", "senegal": "SN",
    "somalia": "SO", "chad": "TD", "zimbabwe": "ZW", "guinea": "GN",
    "rwanda": "RW", "benin": "BJ", "tunisia": "TN", "south sudan": "SS",
    "togo": "TG", "sierra leone": "SL", "libya": "LY", "jordan": "JO",
    "lebanon": "LB", "israel": "IL", "palestine": "PS", "kuwait": "KW",
    "qatar": "QA", "bahrain": "BH", "oman": "OM", "yemen": "YE",
    "iraq": "IQ", "syria": "SY", "afghanistan": "AF", "uzbekistan": "UZ",
    "kazakhstan": "KZ", "turkmenistan": "TM", "kyrgyzstan": "KG", "tajikistan": "TJ",
    "mongolia": "MN", "nepal": "NP", "bhutan": "BT", "maldives": "MV",
    "singapore": "SG", "malaysia": "MY", "brunei": "BN", "cambodia": "KH",
    "laos": "LA", "timor-leste": "TL", "papua new guinea": "PG", "fiji": "FJ",
    "new zealand": "NZ", "chile": "CL", "peru": "PE", "colombia": "CO",
    "venezuela": "VE", "ecuador": "EC", "bolivia": "BO", "paraguay": "PY",
    "uruguay": "UY", "guyana": "GY", "suriname": "SR", "guatemala": "GT",
    "belize": "BZ", "honduras": "HN", "el salvador": "SV", "nicaragua": "NI",
    "costa rica": "CR", "panama": "PA", "cuba": "CU", "jamaica": "JM",
    "haiti": "HT", "dominican republic": "DO", "trinidad and tobago": "TT",
    "barbados": "BB", "saint lucia": "LC", "grenada": "GD", "saint vincent": "VC",
    "antigua and barbuda": "AG", "dominica": "DM", "saint kitts": "KN",
    "bahamas": "BS", "iceland": "IS", "norway": "NO", "denmark": "DK",
    "finland": "FI", "ireland": "IE", "portugal": "PT", "greece": "GR",
    "austria": "AT", "czech republic": "CZ", "czechia": "CZ", "slovakia": "SK",
    "hungary": "HU", "romania": "RO", "bulgaria": "BG", "serbia": "RS",
    "croatia": "HR", "slovenia": "SI", "bosnia": "BA", "north macedonia": "MK",
    "albania": "AL", "montenegro": "ME", "kosovo": "XK", "moldova": "MD",
    "ukraine": "UA", "belarus": "BY", "lithuania": "LT", "latvia": "LV",
    "estonia": "EE", "georgia": "GE", "armenia": "AM", "azerbaijan": "AZ",
    "cyprus": "CY", "malta": "MT", "luxembourg": "LU", "liechtenstein": "LI",
    "monaco": "MC", "andorra": "AD", "san marino": "SM", "vatican": "VA",
    "seychelles": "SC", "mauritius": "MU", "comoros": "KM", "cape verde": "CV",
    "sao tome": "ST", "equatorial guinea": "GQ", "gabon": "GA", "congo": "CG",
    "central african republic": "CF", "djibouti": "DJ", "eritrea": "ER",
    "lesotho": "LS", "eswatini": "SZ", "botswana": "BW", "namibia": "NA",
    "eswatini": "SZ", "mauritania": "MR", "gambia": "GM", "guinea-bissau": "GW",
    "liberia": "LR", "ivory coast": "CI"
}

# ==============================
# SAFE ASYNC REQUEST HELPERS
# ==============================

async def safe_get_json(url, method="GET", json_body=None, timeout=15, headers=None):
    logger.info(f"➡️ {method} JSON: {url[:100]}...")
    try:
        if method == "POST":
            res = await client.post(url, json=json_body, timeout=timeout, headers=headers or {})
        else:
            res = await client.get(url, timeout=timeout, headers=headers or {})
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


async def safe_get_text(url, timeout=15, headers=None):
    logger.info(f"➡️ GET TEXT: {url[:100]}...")
    try:
        res = await client.get(url, timeout=timeout, headers=headers or {})
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


def _mask_token(token: str) -> str:
    if not token:
        return "[none]"
    if len(token) <= 12:
        return "***"
    return token[:8] + "..."


def verify_clerk_token(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        logger.info("🔐 [AUTH] No Bearer token in request")
        return None
    token = auth.split(" ", 1)[1]
    masked = _mask_token(token)
    logger.info(f"🔐 [AUTH] Verifying token: {masked}")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"verify_aud": False, "verify_exp": True}
        )
        logger.info(f"🔐 [AUTH] Token valid for user: {payload.get('email', payload.get('sub', 'unknown'))}")
        return payload
    except Exception as e:
        logger.warning(f"🔐 [AUTH] Token verification failed: {masked} | error: {e}")
        return None


def verify_gateway_secret(request: Request):
    secret = request.headers.get("X-Gateway-Secret", "")
    if not GATEWAY_SECRET:
        logger.warning("⚠️ GATEWAY_SECRET not set — allowing all requests (dev mode)")
        return True
    if secret != GATEWAY_SECRET:
        logger.warning(f"❌ Invalid X-Gateway-Secret: {secret[:8]}...")
        return False
    logger.info("✅ X-Gateway-Secret verified")
    return True


def sanitize_city(city: str) -> str:
    """Sanitize city name for URL safety"""
    if not city:
        return ""
    city = unicodedata.normalize("NFC", city.strip())
    return urllib.parse.quote(city)


def get_country_code(country_name: str) -> str:
    """Map country name to ISO code for holiday APIs"""
    if not country_name:
        return "US"
    normalized = country_name.lower().strip()
    return COUNTRY_TO_CODE.get(normalized, "US")


# ==============================
# COORDINATES — 5 SOURCES (Worldwide)
# ==============================

async def get_coordinates_openmeteo(city):
    """Primary: Open-Meteo Geocoding (Free, no key, worldwide)"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={sanitize_city(city)}&count=5&language=en&format=json"
    res = await safe_get_json(url)
    if not res or "results" not in res or not res["results"]:
        return None
    data = res["results"][0]
    return {
        "city": data.get("name"),
        "country": data.get("country"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone", "UTC"),
        "country_code": data.get("country_code", "US"),
        "elevation": data.get("elevation"),
        "population": data.get("population"),
        "source": "openmeteo"
    }


async def get_coordinates_nominatim(city):
    """Fallback 1: OpenStreetMap Nominatim (Free, worldwide, no key)"""
    url = f"https://nominatim.openstreetmap.org/search?q={sanitize_city(city)}&format=json&limit=1&addressdetails=1"
    headers = {"User-Agent": "GeoBot-MCP/2.0 (contact@example.com)"}
    try:
        res = await client.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return None
        data = res.json()
        if not data or len(data) == 0:
            return None
        place = data[0]
        addr = place.get("address", {})
        country = addr.get("country", "Unknown")
        country_code = addr.get("country_code", "us").upper()
        return {
            "city": addr.get("city") or addr.get("town") or addr.get("village") or city,
            "country": country,
            "latitude": float(place.get("lat", 0)),
            "longitude": float(place.get("lon", 0)),
            "timezone": "UTC",
            "country_code": country_code,
            "elevation": None,
            "population": None,
            "source": "nominatim"
        }
    except Exception as e:
        logger.warning(f"Nominatim failed: {e}")
        return None


async def get_coordinates_geocode_xyz(city):
    """Fallback 2: Geocode.xyz (Free, worldwide, rate limited)"""
    url = f"https://geocode.xyz/{sanitize_city(city)}?json=1&auth=YOUR_AUTH_KEY"
    try:
        res = await client.get(url, timeout=15)
        if res.status_code != 200:
            return None
        data = res.json()
        if "error" in data:
            return None
        country = data.get("standard", {}).get("countryname", "Unknown")
        return {
            "city": data.get("standard", {}).get("city", city),
            "country": country,
            "latitude": float(data.get("latt", 0)),
            "longitude": float(data.get("longt", 0)),
            "timezone": "UTC",
            "country_code": get_country_code(country),
            "elevation": None,
            "population": None,
            "source": "geocode_xyz"
        }
    except Exception as e:
        logger.warning(f"Geocode.xyz failed: {e}")
        return None


async def get_coordinates_positionstack(city):
    """Fallback 3: PositionStack (Free tier: 25k requests/month, worldwide)"""
    api_key = os.environ.get("POSITIONSTACK_API_KEY", "")
    if not api_key:
        return None
    url = f"http://api.positionstack.com/v1/forward?access_key={api_key}&query={sanitize_city(city)}&limit=1"
    try:
        res = await safe_get_json(url)
        if not res or "data" not in res or not res["data"]:
            return None
        data = res["data"][0]
        country = data.get("country", "Unknown")
        return {
            "city": data.get("name", city),
            "country": country,
            "latitude": float(data.get("latitude", 0)),
            "longitude": float(data.get("longitude", 0)),
            "timezone": "UTC",
            "country_code": data.get("country_code", get_country_code(country)),
            "elevation": None,
            "population": None,
            "source": "positionstack"
        }
    except Exception as e:
        logger.warning(f"PositionStack failed: {e}")
        return None


async def get_coordinates_bigdatacloud(city):
    """Fallback 4: BigDataCloud Free Reverse Geocoding (Free, worldwide)"""
    # First get rough coords from a simpler search
    url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?locality={sanitize_city(city)}&localityLanguage=en"
    try:
        res = await safe_get_json(url)
        if not res or not res.get("latitude"):
            return None
        country = res.get("countryName", "Unknown")
        return {
            "city": res.get("city", city),
            "country": country,
            "latitude": float(res.get("latitude", 0)),
            "longitude": float(res.get("longitude", 0)),
            "timezone": res.get("localityInfo", {}).get("informative", [{}])[0].get("description", "UTC") if res.get("localityInfo") else "UTC",
            "country_code": res.get("countryCode", get_country_code(country)),
            "elevation": None,
            "population": None,
            "source": "bigdatacloud"
        }
    except Exception as e:
        logger.warning(f"BigDataCloud failed: {e}")
        return None


async def get_coordinates(city):
    """Try 5 coordinate sources with fallback (Worldwide)"""
    logger.info(f"🌍 Fetching coordinates for: {city}")
    sources = [
        ("Open-Meteo", get_coordinates_openmeteo),
        ("Nominatim", get_coordinates_nominatim),
        ("Geocode.xyz", get_coordinates_geocode_xyz),
        ("PositionStack", get_coordinates_positionstack),
        ("BigDataCloud", get_coordinates_bigdatacloud),
    ]
    for name, fn in sources:
        try:
            logger.info(f"🌍 Trying {name}...")
            result = await fn(city)
            if result and result.get("latitude") and result.get("longitude"):
                logger.info(f"✅ {name} success: {result['city']}, {result['country']}")
                return result
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.error("❌ All coordinate sources failed")
    return None


# ==============================
# WEATHER — 5 SOURCES (Worldwide)
# ==============================

async def get_weather_openmeteo(lat, lon):
    """Primary: Open-Meteo Weather (Free, no key, worldwide)"""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,weather_code,visibility"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_sum"
        f"&timezone=auto&forecast_days=3"
    )
    res = await safe_get_json(url)
    if not res:
        return None
    current = res.get("current", {})
    daily = res.get("daily", {})
    hourly = res.get("hourly", {})

    weather_codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
        77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }

    return {
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "is_day": current.get("is_day"),
        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "snowfall": current.get("snowfall"),
        "weather_code": current.get("weather_code"),
        "weather_description": weather_codes.get(current.get("weather_code"), "Unknown"),
        "cloud_cover": current.get("cloud_cover"),
        "pressure": current.get("pressure_msl"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
        "time": current.get("time"),
        "forecast_3day": {
            "dates": daily.get("time", []),
            "max_temps": daily.get("temperature_2m_max", []),
            "min_temps": daily.get("temperature_2m_min", []),
            "weather_codes": daily.get("weather_code", []),
            "uv_index": daily.get("uv_index_max", []),
            "precipitation": daily.get("precipitation_sum", []),
            "sunrise": daily.get("sunrise", []),
            "sunset": daily.get("sunset", [])
        },
        "source": "openmeteo"
    }


async def get_weather_openweathermap(lat, lon):
    """Fallback 1: OpenWeatherMap (Free tier: 1000 calls/day, worldwide, needs API key)"""
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return None
    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"lat={lat}&lon={lon}&appid={api_key}&units=metric"
    )
    res = await safe_get_json(url)
    if not res or res.get("cod") != 200:
        return None
    main = res.get("main", {})
    wind = res.get("wind", {})
    weather = res.get("weather", [{}])[0]
    return {
        "temperature": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "wind_speed": wind.get("speed"),
        "wind_direction": wind.get("deg"),
        "wind_gusts": wind.get("gust"),
        "weather_code": weather.get("id"),
        "weather_description": weather.get("description", "").title(),
        "cloud_cover": res.get("clouds", {}).get("all"),
        "visibility": res.get("visibility"),
        "time": datetime.utcnow().isoformat(),
        "source": "openweathermap"
    }


async def get_weather_7timer(lat, lon):
    """Fallback 2: 7Timer (Free, no key, worldwide)"""
    url = f"https://www.7timer.info/bin/api.pl?lon={lon}&lat={lat}&product=civil&output=json"
    try:
        res = await safe_get_json(url, timeout=12)
        if not res or "dataseries" not in res or not res["dataseries"]:
            return None
        current = res["dataseries"][0]
        weather_map = {"clear": "Clear", "cloudy": "Cloudy", "rain": "Rain", "snow": "Snow", "storm": "Storm"}
        return {
            "temperature": current.get("temp2m"),
            "humidity": current.get("rh2m"),
            "wind_speed": current.get("wind10m", {}).get("speed"),
            "wind_direction": current.get("wind10m", {}).get("direction"),
            "weather_code": current.get("weather", "clear"),
            "weather_description": weather_map.get(current.get("weather", "clear"), "Unknown"),
            "time": datetime.utcnow().isoformat(),
            "source": "7timer"
        }
    except Exception as e:
        logger.warning(f"7Timer failed: {e}")
        return None


async def get_weather_weatherapi(lat, lon):
    """Fallback 3: WeatherAPI (Free tier: 1M calls/month, worldwide, needs API key)"""
    api_key = os.environ.get("WEATHERAPI_KEY", "")
    if not api_key:
        return None
    url = f"https://api.weatherapi.com/v1/current.json?key={api_key}&q={lat},{lon}&aqi=yes"
    try:
        res = await safe_get_json(url)
        if not res or "current" not in res:
            return None
        current = res["current"]
        return {
            "temperature": current.get("temp_c"),
            "feels_like": current.get("feelslike_c"),
            "humidity": current.get("humidity"),
            "pressure": current.get("pressure_mb"),
            "wind_speed": current.get("wind_kph"),
            "wind_direction": current.get("wind_degree"),
            "weather_description": current.get("condition", {}).get("text", ""),
            "visibility": current.get("vis_km"),
            "uv_index": current.get("uv"),
            "cloud_cover": current.get("cloud"),
            "time": current.get("last_updated"),
            "source": "weatherapi"
        }
    except Exception as e:
        logger.warning(f"WeatherAPI failed: {e}")
        return None


async def get_weather_visualcrossing(lat, lon):
    """Fallback 4: Visual Crossing (Free tier: 1000 records/day, worldwide, needs API key)"""
    api_key = os.environ.get("VISUALCROSSING_KEY", "")
    if not api_key:
        return None
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}/today?unitGroup=metric&include=current&key={api_key}&contentType=json"
    try:
        res = await safe_get_json(url)
        if not res or "currentConditions" not in res:
            return None
        current = res["currentConditions"]
        return {
            "temperature": current.get("temp"),
            "feels_like": current.get("feelslike"),
            "humidity": current.get("humidity"),
            "pressure": current.get("pressure"),
            "wind_speed": current.get("windspeed"),
            "wind_direction": current.get("winddir"),
            "weather_description": current.get("conditions", ""),
            "visibility": current.get("visibility"),
            "uv_index": current.get("uvindex"),
            "cloud_cover": current.get("cloudcover"),
            "time": current.get("datetime"),
            "source": "visualcrossing"
        }
    except Exception as e:
        logger.warning(f"VisualCrossing failed: {e}")
        return None


async def get_weather(lat, lon):
    """Try 5 weather sources with fallback (Worldwide)"""
    logger.info(f"🌡 Fetching weather for: {lat}, {lon}")
    sources = [
        ("Open-Meteo", get_weather_openmeteo),
        ("OpenWeatherMap", get_weather_openweathermap),
        ("WeatherAPI", get_weather_weatherapi),
        ("VisualCrossing", get_weather_visualcrossing),
        ("7Timer", get_weather_7timer),
    ]
    for name, fn in sources:
        try:
            logger.info(f"🌡 Trying {name}...")
            result = await fn(lat, lon)
            if result and result.get("temperature") is not None:
                logger.info(f"✅ {name} success: {result['temperature']}°C")
                return result
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.error("❌ All weather sources failed")
    return None


# ==============================
# AQI — 4 SOURCES (Worldwide)
# ==============================

async def get_aqi_openmeteo(lat, lon):
    """Primary: Open-Meteo Air Quality (Free, no key, worldwide)"""
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?"
        f"latitude={lat}&longitude={lon}"
        f"&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi,european_aqi"
        f"&timezone=auto"
    )
    res = await safe_get_json(url)
    if not res or "current" not in res:
        return None
    current = res["current"]
    return {
        "pm10": current.get("pm10"),
        "pm2_5": current.get("pm2_5"),
        "co": current.get("carbon_monoxide"),
        "no2": current.get("nitrogen_dioxide"),
        "so2": current.get("sulphur_dioxide"),
        "o3": current.get("ozone"),
        "us_aqi": current.get("us_aqi"),
        "eu_aqi": current.get("european_aqi"),
        "time": current.get("time"),
        "source": "openmeteo_aqi"
    }


async def get_aqi_waqi(lat, lon):
    """Fallback 1: WAQI (World Air Quality Index) - Free demo token, worldwide"""
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token=demo"
    try:
        res = await safe_get_json(url, timeout=12)
        if not res or res.get("status") != "ok":
            return None
        data = res.get("data", {})
        iaqi = data.get("iaqi", {})
        return {
            "pm10": iaqi.get("pm10", {}).get("v"),
            "pm2_5": iaqi.get("pm25", {}).get("v"),
            "co": iaqi.get("co", {}).get("v"),
            "no2": iaqi.get("no2", {}).get("v"),
            "so2": iaqi.get("so2", {}).get("v"),
            "o3": iaqi.get("o3", {}).get("v"),
            "us_aqi": data.get("aqi"),
            "station": data.get("city", {}).get("name"),
            "time": data.get("time", {}).get("iso"),
            "source": "waqi"
        }
    except Exception as e:
        logger.warning(f"WAQI failed: {e}")
        return None


async def get_aqi_openweathermap(lat, lon):
    """Fallback 2: OpenWeatherMap Air Pollution (Free, needs API key, worldwide)"""
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return None
    url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
    try:
        res = await safe_get_json(url)
        if not res or "list" not in res or not res["list"]:
            return None
        data = res["list"][0]
        main = data.get("main", {})
        components = data.get("components", {})
        aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
        return {
            "us_aqi": main.get("aqi"),
            "aqi_label": aqi_labels.get(main.get("aqi"), "Unknown"),
            "co": components.get("co"),
            "no": components.get("no"),
            "no2": components.get("no2"),
            "o3": components.get("o3"),
            "so2": components.get("so2"),
            "pm2_5": components.get("pm2_5"),
            "pm10": components.get("pm10"),
            "nh3": components.get("nh3"),
            "time": datetime.utcnow().isoformat(),
            "source": "openweathermap_aqi"
        }
    except Exception as e:
        logger.warning(f"OpenWeatherMap AQI failed: {e}")
        return None


async def get_aqi_purpleair(lat, lon):
    """Fallback 3: PurpleAir (Free, needs API key, worldwide sensor network)"""
    api_key = os.environ.get("PURPLEAIR_KEY", "")
    if not api_key:
        return None
    url = f"https://api.purpleair.com/v1/sensors?fields=pm2.5,pm10.0,temperature,humidity,pressure&location_type=0&nwlng={lon-0.5}&nwlat={lat+0.5}&selng={lon+0.5}&selat={lat-0.5}"
    headers = {"X-API-Key": api_key}
    try:
        res = await safe_get_json(url, headers=headers)
        if not res or "data" not in res or not res["data"]:
            return None
        sensor = res["data"][0]
        return {
            "pm2_5": sensor[1] if len(sensor) > 1 else None,
            "pm10": sensor[2] if len(sensor) > 2 else None,
            "temperature": sensor[3] if len(sensor) > 3 else None,
            "humidity": sensor[4] if len(sensor) > 4 else None,
            "pressure": sensor[5] if len(sensor) > 5 else None,
            "time": datetime.utcnow().isoformat(),
            "source": "purpleair"
        }
    except Exception as e:
        logger.warning(f"PurpleAir failed: {e}")
        return None


async def get_aqi(lat, lon):
    """Try 4 AQI sources with fallback (Worldwide)"""
    logger.info(f"🌫 Fetching AQI for: {lat}, {lon}")
    sources = [
        ("Open-Meteo AQI", get_aqi_openmeteo),
        ("WAQI", get_aqi_waqi),
        ("OpenWeatherMap AQI", get_aqi_openweathermap),
        ("PurpleAir", get_aqi_purpleair),
    ]
    for name, fn in sources:
        try:
            logger.info(f"🌫 Trying {name}...")
            result = await fn(lat, lon)
            if result and (result.get("us_aqi") or result.get("pm2_5") or result.get("pm10")):
                logger.info(f"✅ {name} success")
                return result
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.warning("⚠️ All AQI sources failed")
    return None


# ==============================
# TIME (Worldwide)
# ==============================

def get_time(timezone):
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return {
            "formatted": now.strftime("%d %B %Y, %I:%M %p"),
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%I:%M %p"),
            "day_of_week": now.strftime("%A"),
            "week_number": now.isocalendar()[1],
            "timezone": timezone,
            "utc_offset": now.strftime("%z")
        }
    except Exception as e:
        logger.exception(f"❌ Time error: {e}")
        return None


# ==============================
# HOLIDAY — 3 SOURCES (Worldwide)
# ==============================

async def get_today_holiday_nager(country_code="US"):
    """Primary: Nager.Date API (Free, worldwide, 100+ countries)"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    year = today[:4]
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    res = await safe_get_json(url)
    if not res:
        return None
    for holiday in res:
        if holiday.get("date") == today:
            return {
                "name": holiday.get("localName"),
                "english_name": holiday.get("name"),
                "country_code": country_code,
                "global": holiday.get("global", True),
                "types": holiday.get("types", []),
                "source": "nager"
            }
    return None


async def get_today_holiday_calendarific(country_code="US"):
    """Fallback 1: Calendarific (Free tier: 1000 calls/month, 230+ countries, needs API key)"""
    api_key = os.environ.get("CALENDARIFIC_KEY", "")
    if not api_key:
        return None
    today = datetime.utcnow()
    url = (
        f"https://calendarific.com/api/v2/holidays?"
        f"api_key={api_key}&country={country_code}&year={today.year}&month={today.month}&day={today.day}"
    )
    try:
        res = await safe_get_json(url)
        if not res or "response" not in res or "holidays" not in res["response"]:
            return None
        holidays = res["response"]["holidays"]
        if not holidays:
            return None
        h = holidays[0]
        return {
            "name": h.get("name"),
            "english_name": h.get("name"),
            "country_code": country_code,
            "global": True,
            "types": [h.get("type", "")],
            "source": "calendarific"
        }
    except Exception as e:
        logger.warning(f"Calendarific failed: {e}")
        return None


async def get_today_holiday_abstract(country_code="US"):
    """Fallback 2: Abstract API (Free tier: 5000 requests/month, 230+ countries, needs API key)"""
    api_key = os.environ.get("ABSTRACT_API_KEY", "")
    if not api_key:
        return None
    today = datetime.utcnow()
    url = (
        f"https://holidays.abstractapi.com/v1/?"
        f"api_key={api_key}&country={country_code}&year={today.year}&month={today.month}&day={today.day}"
    )
    try:
        res = await safe_get_json(url)
        if not res or not isinstance(res, list) or len(res) == 0:
            return None
        h = res[0]
        return {
            "name": h.get("name"),
            "english_name": h.get("name"),
            "country_code": country_code,
            "global": True,
            "types": [h.get("type", "")],
            "source": "abstract"
        }
    except Exception as e:
        logger.warning(f"Abstract API failed: {e}")
        return None


async def get_today_holiday(country_code="US"):
    """Try 3 holiday sources with fallback (Worldwide)"""
    sources = [
        ("Nager.Date", get_today_holiday_nager),
        ("Calendarific", get_today_holiday_calendarific),
        ("Abstract API", get_today_holiday_abstract),
    ]
    for name, fn in sources:
        try:
            logger.info(f"🎉 Trying {name} for {country_code}...")
            result = await fn(country_code)
            if result:
                logger.info(f"✅ {name} success: {result['name']}")
                return result
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.warning("⚠️ All holiday sources failed")
    return None


# ==============================
# FACTS — 3 SOURCES (Worldwide)
# ==============================

async def get_today_fact_numbersapi():
    """Primary: Numbers API (Free, no key)"""
    today = datetime.utcnow()
    url = f"http://numbersapi.com/{today.month}/{today.day}/date"
    text = await safe_get_text(url)
    if text:
        return {"text": text.strip(), "source": "numbersapi"}
    return None


async def get_today_fact_wikipedia():
    """Fallback 1: Wikipedia 'On this day' (Free, worldwide)"""
    today = datetime.utcnow()
    month_name = today.strftime("%B")
    day = today.day
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month_name}/{day}"
    try:
        res = await safe_get_json(url, timeout=12)
        if not res or "events" not in res or not res["events"]:
            return None
        event = res["events"][0]
        year = event.get("year", "")
        text = event.get("text", "")
        pages = event.get("pages", [])
        related = [p.get("titles", {}).get("normalized", "") for p in pages[:3] if p.get("titles")]
        return {
            "text": f"In {year}, {text}",
            "year": year,
            "related_topics": related,
            "source": "wikipedia"
        }
    except Exception as e:
        logger.warning(f"Wikipedia facts failed: {e}")
        return None


async def get_today_fact_history_com():
    """Fallback 2: History.com 'This Day in History' (Free, web scraping fallback)"""
    today = datetime.utcnow()
    month = today.strftime("%B").lower()
    day = today.day
    url = f"https://www.history.com/this-day-in-history/{month}-{day}"
    try:
        text = await safe_get_text(url, timeout=12)
        if not text:
            return None
        # Simple extraction - in production use BeautifulSoup
        import re
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            return {
                "text": title,
                "source": "historycom"
            }
        return None
    except Exception as e:
        logger.warning(f"History.com failed: {e}")
        return None


async def get_today_fact():
    """Try 3 fact sources with fallback"""
    sources = [
        ("Numbers API", get_today_fact_numbersapi),
        ("Wikipedia", get_today_fact_wikipedia),
        ("History.com", get_today_fact_history_com),
    ]
    for name, fn in sources:
        try:
            logger.info(f"📚 Trying {name}...")
            result = await fn()
            if result and result.get("text"):
                logger.info(f"✅ {name} success")
                return result
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.warning("⚠️ All fact sources failed")
    return None


# ==============================
# NEW: EXCHANGE RATES (Worldwide)
# ==============================

async def get_exchange_rates():
    """Fetch current exchange rates (Free, no key, worldwide)"""
    logger.info("💱 Fetching exchange rates...")
    sources = [
        ("ExchangeRate-API", "https://api.exchangerate-api.com/v4/latest/USD"),
        ("Frankfurter", "https://api.frankfurter.app/latest"),
        ("Open.er", "https://open.er-api.com/v6/latest/USD"),
    ]
    for name, url in sources:
        try:
            res = await safe_get_json(url, timeout=10)
            if res and res.get("rates"):
                logger.info(f"✅ {name} success")
                rates = res.get("rates", {})
                return {
                    "base": res.get("base", "USD"),
                    "date": res.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
                    "rates": {
                        "EUR": rates.get("EUR"),
                        "GBP": rates.get("GBP"),
                        "JPY": rates.get("JPY"),
                        "CNY": rates.get("CNY"),
                        "INR": rates.get("INR"),
                        "AUD": rates.get("AUD"),
                        "CAD": rates.get("CAD"),
                        "CHF": rates.get("CHF"),
                        "SEK": rates.get("SEK"),
                        "NZD": rates.get("NZD"),
                        "SGD": rates.get("SGD"),
                        "HKD": rates.get("HKD"),
                        "KRW": rates.get("KRW"),
                        "BRL": rates.get("BRL"),
                        "MXN": rates.get("MXN"),
                        "ZAR": rates.get("ZAR"),
                        "RUB": rates.get("RUB"),
                    },
                    "source": name.lower().replace("-", "_").replace(".", "_")
                }
        except Exception as e:
            logger.warning(f"❌ {name} failed: {e}")
    logger.warning("⚠️ All exchange rate sources failed")
    return None


# ==============================
# NEW: NEWS (Worldwide)
# ==============================

async def get_news_gnews(country_code="US"):
    """Fetch top headlines (Free tier: 100 requests/day, needs API key)"""
    api_key = os.environ.get("GNEWS_API_KEY", "")
    if not api_key:
        return None
    url = f"https://gnews.io/api/v4/top-headlines?country={country_code}&max=5&apikey={api_key}"
    try:
        res = await safe_get_json(url)
        if not res or "articles" not in res:
            return None
        articles = []
        for article in res["articles"][:5]:
            articles.append({
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url"),
                "published_at": article.get("publishedAt"),
                "source": article.get("source", {}).get("name")
            })
        return {
            "articles": articles,
            "total": res.get("totalArticles", 0),
            "source": "gnews"
        }
    except Exception as e:
        logger.warning(f"GNews failed: {e}")
        return None


async def get_news(country_code="US"):
    """Try news sources"""
    logger.info(f"📰 Fetching news for {country_code}...")
    result = await get_news_gnews(country_code)
    if result:
        logger.info(f"✅ News fetched: {result['total']} articles")
        return result
    logger.warning("⚠️ News sources failed")
    return None


# ==============================
# NEW: COUNTRY INFO (Worldwide)
# ==============================

async def get_country_info(country_code):
    """Fetch country details from REST Countries (Free, no key, worldwide)"""
    logger.info(f"🌐 Fetching country info for {country_code}...")
    url = f"https://restcountries.com/v3.1/alpha/{country_code}"
    try:
        res = await safe_get_json(url)
        if not res or not isinstance(res, list) or len(res) == 0:
            return None
        data = res[0]
        return {
            "name": data.get("name", {}).get("common"),
            "official_name": data.get("name", {}).get("official"),
            "capital": data.get("capital", ["Unknown"])[0] if data.get("capital") else "Unknown",
            "region": data.get("region"),
            "subregion": data.get("subregion"),
            "population": data.get("population"),
            "area": data.get("area"),
            "currency": list(data.get("currencies", {}).keys())[0] if data.get("currencies") else None,
            "language": list(data.get("languages", {}).values())[0] if data.get("languages") else None,
            "flag": data.get("flags", {}).get("png"),
            "coat_of_arms": data.get("coatOfArms", {}).get("png"),
            "driving_side": data.get("car", {}).get("side"),
            "timezones": data.get("timezones", []),
            "borders": data.get("borders", []),
            "source": "restcountries"
        }
    except Exception as e:
        logger.warning(f"REST Countries failed: {e}")
        return None


# ==============================
# KEEP-ALIVE (Self-ping)
# ==============================

SELF_URL = os.environ.get("SELF_URL", "")
KEEP_ALIVE_INTERVAL = 540

async def keep_alive_loop():
    logger.info(f"♻️ Keep-alive started — pinging {SELF_URL} every {KEEP_ALIVE_INTERVAL // 60} minutes")
    await asyncio.sleep(30)
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as ping_client:
                ping_url = SELF_URL.replace("/tool", "/ping")
                response = await ping_client.get(ping_url, timeout=15)
                if response.status_code == 200:
                    logger.info("♻️ Keep-alive ping successful")
                else:
                    logger.warning(f"♻️ Keep-alive ping returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"♻️ Keep-alive ping failed: {e}")
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_loop())
    logger.info("🚀 MCP Server V9-WORLDWIDE startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()
    logger.info("👋 MCP Server shutting down, client closed")


# ==============================
# PUBLIC PING
# ==============================

@app.get("/ping")
@app.head("/ping")
def ping():
    return {"status": "ok", "version": "v9-worldwide"}


# ==============================
# HEALTH (protected)
# ==============================

@app.get("/health")
@app.head("/health")
def health(request: Request):
    user = verify_clerk_token(request)
    if not user:
        return JSONResponse(
            {"error": "Unauthorized — valid Bearer token required"},
            status_code=401
        )
    logger.info(f"🔐 [AUTH] /health accessed by: {user.get('email', user.get('sub', 'unknown'))}")
    return {"status": "ok", "version": "v9-worldwide"}


# ==============================
# TOOL HANDLER (protected)
# ==============================

@app.post("/tool")
async def tool_handler(request: Request):
    # 1. Verify Gateway Secret FIRST
    if not verify_gateway_secret(request):
        logger.warning("❌ [GATEWAY] /tool rejected — invalid gateway secret")
        return JSONResponse(
            {"error": "Unauthorized — Invalid gateway secret"},
            status_code=401
        )

    # 2. Verify Bearer token
    user = verify_clerk_token(request)
    if not user:
        logger.warning("🔐 [AUTH] /tool rejected — no valid token")
        return JSONResponse(
            {"error": "Unauthorized — valid Bearer token required"},
            status_code=401
        )
    logger.info(f"🔐 [AUTH] /tool accessed by: {user.get('email', user.get('sub', 'unknown'))}")

    try:
        payload = await request.json()
        logger.info("🔥 MCP SERVER HIT")
        logger.info(json.dumps(payload, indent=2))

        tool = payload.get("tool")
        city = payload.get("input")
        include_extras = payload.get("extras", True)  # New: toggle extra data

        # HEALTH CHECK
        if tool == "healthCheck":
            return {
                "status": "ok",
                "server": "MCP ASYNC RUNNING",
                "version": "V9-WORLDWIDE",
                "features": {
                    "coordinates": ["openmeteo", "nominatim", "geocode_xyz", "positionstack", "bigdatacloud"],
                    "weather": ["openmeteo", "openweathermap", "weatherapi", "visualcrossing", "7timer"],
                    "aqi": ["openmeteo_aqi", "waqi", "openweathermap_aqi", "purpleair"],
                    "holiday": ["nager", "calendarific", "abstract"],
                    "facts": ["numbersapi", "wikipedia", "historycom"],
                    "exchange_rates": ["exchangerate_api", "frankfurter", "open_er"],
                    "news": ["gnews"],
                    "country_info": ["restcountries"]
                }
            }

        if not city:
            return {"error": "No city provided"}

        coord = await get_coordinates(city)

        if not coord:
            return {"error": "City not found — tried Open-Meteo, Nominatim, Geocode.xyz, PositionStack, and BigDataCloud"}

        lat = coord["latitude"]
        lon = coord["longitude"]
        country_code = coord.get("country_code", "US")

        # PARALLEL EXECUTION
        weather_task = get_weather(lat, lon)
        aqi_task = get_aqi(lat, lon)
        holiday_task = get_today_holiday(country_code)
        fact_task = get_today_fact()
        country_info_task = get_country_info(country_code)

        # Only fetch extras if requested (saves API calls)
        exchange_task = get_exchange_rates() if include_extras else asyncio.sleep(0)
        news_task = get_news(country_code) if include_extras else asyncio.sleep(0)

        weather, aqi, holiday, fact, country_info, exchange_rates, news = await asyncio.gather(
            weather_task,
            aqi_task,
            holiday_task,
            fact_task,
            country_info_task,
            exchange_task,
            news_task
        )

        result = {
            "source": "MCP_SERVER_V9_WORLDWIDE",
            "city": coord["city"],
            "country": coord["country"],
            "country_code": country_code,
            "latitude": lat,
            "longitude": lon,
            "timezone": coord.get("timezone", "UTC"),
        }

        if coord.get("elevation"):
            result["elevation_meters"] = coord["elevation"]
        if coord.get("population"):
            result["population"] = coord["population"]

        if weather:
            result["weather"] = weather

        if aqi:
            result["air_quality"] = aqi

        current_time = get_time(coord["timezone"])
        if current_time:
            result["current_time"] = current_time

        special = {}
        if holiday:
            special["holiday"] = holiday
        if fact:
            special["today_in_history"] = fact

        if special:
            result["today_special"] = special

        if country_info:
            result["country_info"] = country_info

        if include_extras:
            if exchange_rates:
                result["exchange_rates"] = exchange_rates
            if news:
                result["news"] = news

        logger.info("✅ Final Response:")
        logger.info(json.dumps(result, indent=2))

        return result

    except Exception as e:
        logger.exception(f"💥 CRITICAL ERROR: {e}")
        return {"error": "Internal server error"}