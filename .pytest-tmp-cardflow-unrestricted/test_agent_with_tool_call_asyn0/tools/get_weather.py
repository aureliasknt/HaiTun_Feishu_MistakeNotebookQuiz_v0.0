async def get_weather(city: str) -> str:
    """Get weather for a city.

    Args:
        city: The city name.
    """
    return f"Weather in {city}: sunny, 22 C"
