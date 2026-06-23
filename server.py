import requests
import json
import re
import os
from groq import Groq

# ==============================
# 🎨 COLORS
# ==============================
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


# ==============================
# 🔗 CONFIG
# ==============================
MCP_URL = "https://mcp-weather-s1s0.onrender.com/tool"

# ✅ USE ENV VARIABLE (IMPORTANT)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    print("❌ Set GROQ_API_KEY environment variable first")
    raise SystemExit(1)

client = Groq(api_key=GROQ_API_KEY)


MODEL = "llama-3.1-8b-instant"


# ==============================
# 🧠 TOOL SELECTION
# ==============================
def choose_tool(user_input):
    text = user_input.lower()

    if "aqi" in text or "air" in text:
        return "getAQI"
    elif "time" in text:
        return "getTimeOnly"
    elif "coordinate" in text:
        return "getCoordinatesOnly"
    elif "weather" in text:
        return "getWeatherOnly"
    elif "today" in text or "holiday" in text:
        return "getTodaySpecial"
    else:
        return "getFullInsights"


# ==============================
# 🌍 CITY EXTRACTION (FIXED)
# ==============================
def extract_cities(user_input):
    words = re.findall(r"[A-Za-z]+", user_input)

    ignore = {
        "weather", "today", "tell", "me", "what", "is",
        "the", "in", "show", "give", "details"
    }

    cities = [w.capitalize() for w in words if w.lower() not in ignore]

    print(f"{Color.YELLOW}🔍 Detected cities: {cities}{Color.END}")
    return cities


# ==============================
# 🔧 MCP CALL (FIXED)
# ==============================
def call_mcp(tool, city):
    try:
        print(f"{Color.CYAN}📡 Calling MCP: {tool} → {city}{Color.END}")

        res = requests.post(
            MCP_URL,
            json={"tool": tool, "input": city},
            timeout=15
        )

        if res.status_code != 200:
            return {"error": f"HTTP {res.status_code}"}

        data = res.json()

        if not data:
            return {"error": "Empty MCP response"}

        return data

    except Exception as e:
        return {"error": str(e)}


# ==============================
# 🧹 CLEAN DATA
# ==============================
def clean_data(data):
    if not isinstance(data, dict):
        return {"error": "Invalid MCP format"}

    cleaned = {}

    for k, v in data.items():
        if v is None:
            continue
        cleaned[k] = v

    cleaned.setdefault("country", "India")

    return cleaned


# ==============================
# 🧠 PROMPT
# ==============================
def build_prompt(user_query, mcp_data):
    return f"""
FORMAT STRICT:

📍 Location: City, Country
🌡 Weather:
🌫 Air Quality:
🕒 Time:
🎉 Highlights:

DATA:
{json.dumps(mcp_data, indent=2)}

USER:
{user_query}
"""


# ==============================
# 🤖 GROQ RESPONSE (FIXED)
# ==============================
def generate_llm_response(prompt):
    try:
        print(f"{Color.GREEN}⚡ Generating response...{Color.END}")

        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Format data cleanly."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            stream=True
        )

        full = ""

        for chunk in completion:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if not delta:
                continue

            token = delta.content

            if token:
                print(token, end="", flush=True)
                full += token

        if not full:
            print("❌ Empty LLM response")

        print("\n")
        return full

    except Exception as e:
        print(f"{Color.RED}❌ Groq Error: {e}{Color.END}")
        return ""


# ==============================
# 🚀 CLI
# ==============================
def start_cli():
    print(f"{Color.GREEN}{Color.BOLD}🚀 MCP + Groq Agent Ready{Color.END}\n")

    while True:
        user_input = input(f"{Color.CYAN}{Color.BOLD}You:{Color.END} ")

        if user_input.lower() == "exit":
            print("👋 Bye!")
            break

        cities = extract_cities(user_input)

        if not cities:
            print(f"{Color.RED}❌ No city found{Color.END}")
            continue

        if len(cities) > 1:
            print(f"{Color.YELLOW}🔍 Multi-city mode{Color.END}")

            results = []
            for city in cities:
                data = call_mcp("getFullInsights", city)

                if "error" in data:
                    print(f"{Color.RED}{city}: {data['error']}{Color.END}")
                    continue

                results.append({city: clean_data(data)})

            if not results:
                print("❌ No valid data")
                continue

            prompt = build_prompt(user_input, results)

        else:
            city = cities[0]
            tool = choose_tool(user_input)

            data = call_mcp(tool, city)

            if "error" in data:
                print(f"{Color.RED}{data['error']}{Color.END}")
                continue

            prompt = build_prompt(user_input, clean_data(data))

        print(f"\n{Color.GREEN}🤖 AI:{Color.END}\n")
        generate_llm_response(prompt)


# ==============================
# ▶️ ENTRY
# ==============================
if __name__ == "__main__":
    start_cli()

# ==============================
def run_agent():
    start_cli()    
