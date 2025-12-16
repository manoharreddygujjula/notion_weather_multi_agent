
from typing import Dict, Literal, Any
from fastmcp import FastMCP
import httpx

mcp=FastMCP("weather_agent")


@mcp.tool()
async def get_weather(
        city: str,
        units: Literal["metric", "imperial"],
        lang: str="en"
) -> Dict[str, Any]:
    """
    Returns current weather from wttr.in.
    Returns temperature, humidity, wind, description and feels-like.
    """
    flags="m" if units=="metric" else ""
    url= f"https://wttr.in/{city}?formate=j1&{flags}&lang={lang}"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r=await client.get(url)
            r.raise_for_status()
            data=r.json()
        cur = (data.get("current_condition") or [{}])[0]
        desc=""

        if cur.get(f"lang_{lang}"):
            desc=cur.get[f"lang_{lang}"][0].get("value","")
        elif cur.get("weatherDesc"):
            desc=cur["weatherDesc"][0].get("value","")

        return {
            "ok":True,
            "weather":{
                "city":city,
                "desc":desc,
                "temp_c":cur.get("temp_c"),
                "temp_f":cur.get("temp_f"),
                "feels_like_c": cur.get("FeelsLikeC"),
                "feels_like_f": cur.get("FeelsLikeF"),
                "humidity_pct": cur.get("humidity"),
                "wind_kmph": cur.get("windspeedKmph"),
                "wind_mph": cur.get("windspeedMiles"),
                "observation_time_utc": cur.get("observation_time"),
                "units": units,
            },
        }
    except Exception as e:
        return {"ok":False, "error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1",port=3000)

