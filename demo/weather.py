# mypy: ignore-errors

import asyncio
import sys
from datetime import date, datetime

import requests

from hygroup.utils import arun


async def get_weather_forecast(city_name: str, target_date: str | None = None) -> str:
    """
    Get the weather forecast for a specific city on a given date.

    Args:
        city_name (str): The name of the city to get the forecast for
        target_date (str, optional): The date for the forecast in YYYY-MM-DD format.
                                    Cannot be in the past. If None, today's date will be used.

    Returns:
        str: A formatted string containing the weather forecast or an error message.
    """
    result = await arun(get_weather_forecast_dict, city_name, target_date)
    return render_weather_forecast(result)


def get_weather_forecast_dict(city_name: str, target_date: str | None = None) -> dict:
    result = {"success": False, "error": None, "city": city_name, "date": target_date, "daily": None, "hourly": None}

    # If target_date is None, use today's date
    if target_date is None:
        today = date.today()
        target_date = today.strftime("%Y-%m-%d")
        print(f"No date specified. Using today's date: {target_date}")
        result["date"] = target_date

    try:
        # Return error if target_date is in the past
        if datetime.strptime(target_date, "%Y-%m-%d").date() < date.today():
            result["error"] = "Target date cannot be in the past."
            return result

        # Step 1: Get coordinates for the city using the geocoding API
        print(f"Looking up coordinates for {city_name}...")
        geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocoding_params = {"name": city_name, "count": 1, "language": "en", "format": "json"}

        geocoding_response = requests.get(geocoding_url, params=geocoding_params)
        geocoding_data = geocoding_response.json()

        # Check if geocoding was successful
        if "results" not in geocoding_data or not geocoding_data["results"]:
            result["error"] = f"Could not find coordinates for {city_name}"
            return result

        # Extract location information
        location = geocoding_data["results"][0]
        latitude = location["latitude"]
        longitude = location["longitude"]
        full_city_name = location["name"]
        country = location.get("country", "")

        result["city_info"] = {
            "name": full_city_name,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": location.get("timezone", "UTC"),
        }

        print(f"Found coordinates for {full_city_name}, {country}: {latitude}, {longitude}")

        # Step 2: Get weather forecast for the target date using the forecast API
        print(f"Retrieving weather forecast for {target_date}...")
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        forecast_params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
            "timezone": location.get("timezone", "UTC"),
            "start_date": target_date,
            "end_date": target_date,
        }

        forecast_response = requests.get(forecast_url, params=forecast_params)
        forecast_data = forecast_response.json()

        # Check if forecast request was successful
        if "error" in forecast_data:
            result["error"] = f"API Error: {forecast_data['reason']}"
            return result

        # Weather code mapping
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }

        # Process daily data if available
        if "daily" in forecast_data:
            daily = forecast_data["daily"]
            daily_date = daily["time"][0]
            daily_weather_code = daily["weather_code"][0]
            daily_temp_max = daily["temperature_2m_max"][0]
            daily_temp_min = daily["temperature_2m_min"][0]
            daily_precip_sum = daily["precipitation_sum"][0]
            daily_precip_prob = daily["precipitation_probability_max"][0]
            daily_wind_speed_max = daily["wind_speed_10m_max"][0]

            weather_description = weather_codes.get(daily_weather_code, "Unknown")

            result["daily"] = {
                "date": daily_date,
                "weather_code": daily_weather_code,
                "weather_description": weather_description,
                "temperature_max": daily_temp_max,
                "temperature_min": daily_temp_min,
                "precipitation_sum": daily_precip_sum,
                "precipitation_probability": daily_precip_prob,
                "wind_speed_max": daily_wind_speed_max,
            }

        # Process hourly data if available
        if "hourly" in forecast_data:
            hourly = forecast_data["hourly"]
            hourly_times = hourly["time"]
            hourly_temps = hourly["temperature_2m"]
            hourly_humidity = hourly["relative_humidity_2m"]
            hourly_precip_prob = hourly["precipitation_probability"]
            hourly_precip = hourly["precipitation"]
            hourly_weather_code = hourly["weather_code"]
            hourly_wind_speed = hourly["wind_speed_10m"]

            # Create a list to hold formatted hourly data
            hourly_data = []
            for i in range(len(hourly_times)):
                time_str = hourly_times[i]
                if target_date in time_str:  # Only include hours for our target date
                    hour = time_str.split("T")[1][:5]  # Extract HH:MM from the time string
                    weather_code = hourly_weather_code[i]
                    weather_desc = weather_codes.get(weather_code, "Unknown")

                    hourly_data.append(
                        {
                            "time": hour,
                            "temperature": hourly_temps[i],
                            "humidity": hourly_humidity[i],
                            "precipitation": hourly_precip[i],
                            "precipitation_probability": hourly_precip_prob[i],
                            "weather_code": weather_code,
                            "weather_description": weather_desc,
                            "wind_speed": hourly_wind_speed[i],
                        }
                    )

            result["hourly"] = hourly_data

        result["success"] = True
        return result

    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        return result


def render_weather_forecast(forecast_result) -> str:
    """
    Formats the weather forecast into a string.

    Args:
        forecast_result (dict): The forecast result returned by get_weather_forecast

    Returns:
        str: A string containing the formatted weather forecast, or an error message.
    """
    if not forecast_result["success"]:
        return f"Error: {forecast_result['error']}"

    output = []
    city_info = forecast_result["city_info"]
    daily = forecast_result["daily"]
    hourly = forecast_result["hourly"]
    target_date = forecast_result["date"]

    output.append(
        f"\n🌦️ WEATHER FORECAST FOR {city_info['name'].upper()}, {city_info['country'].upper()} ON {target_date} 🌦️"
    )
    output.append("=" * 60)

    # Display daily summary
    if daily:
        output.append(f"🌡️ Temperature: {daily['temperature_min']:.1f}°C to {daily['temperature_max']:.1f}°C")
        output.append(f"🌤️ Weather Condition: {daily['weather_description']}")
        output.append(f"💧 Precipitation: {daily['precipitation_sum']:.1f} mm")
        output.append(f"🌧️ Chance of Precipitation: {daily['precipitation_probability']:.0f}%")
        output.append(f"💨 Maximum Wind Speed: {daily['wind_speed_max']:.1f} km/h")
        output.append("=" * 60)

        # Provide a human-readable summary
        output.append("\nSUMMARY:")
        if daily["temperature_max"] > 25:
            temp_desc = "warm"
        elif daily["temperature_max"] > 20:
            temp_desc = "mild"
        else:
            temp_desc = "cool"

        if daily["precipitation_probability"] > 70:
            rain_desc = "very likely"
        elif daily["precipitation_probability"] > 30:
            rain_desc = "possible"
        else:
            rain_desc = "unlikely"

        target_date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        target_date_formatted = target_date_obj.strftime("%B %d, %Y")

        output.append(
            f"{target_date_formatted} in {city_info['name']} is expected to be a {temp_desc} day with {daily['weather_description'].lower()}."
        )
        output.append(
            f"Temperatures will range from {daily['temperature_min']:.1f}°C in the early morning to {daily['temperature_max']:.1f}°C in the afternoon."
        )
        if daily["precipitation_sum"] > 0 or daily["precipitation_probability"] > 0:
            output.append(
                f"Precipitation is {rain_desc} with a {daily['precipitation_probability']:.0f}% chance and potential accumulation of {daily['precipitation_sum']:.1f} mm."
            )
        else:
            output.append("No precipitation is expected.")
        output.append(f"Wind speeds may reach up to {daily['wind_speed_max']:.1f} km/h.")

    # Display hourly breakdown
    if hourly:
        output.append("\nHourly Breakdown:")
        output.append("=" * 60)
        for i, data in enumerate(hourly):
            if i % 3 == 0:  # Display every 3 hours to keep output manageable
                output.append(
                    f"{data['time']}: {data['temperature']:.1f}°C, {data['weather_description']}, "
                    + f"Rain: {data['precipitation']:.1f}mm ({data['precipitation_probability']:.0f}%), "
                    + f"Wind: {data['wind_speed']:.1f} km/h"
                )

    # Check if this is a future forecast
    today = date.today()
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    days_ahead = (target_date_obj - today).days

    if days_ahead > 7:
        output.append("\nNote: This is a long-term forecast and may change as the date approaches.")
        output.append("Weather predictions become less reliable the further into the future they extend.")

    return "\n".join(output)


def main():
    """Main function to run the script from command line"""

    city_name = "graz"
    target_date = "2025-06-17"

    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            print("Error: Date must be in YYYY-MM-DD format")
            sys.exit(1)

    forecast = asyncio.run(get_weather_forecast(city_name, target_date))
    print(forecast)


if __name__ == "__main__":
    main()
