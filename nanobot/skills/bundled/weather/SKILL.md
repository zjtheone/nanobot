---
name: weather
description: Get current weather and forecasts
emoji: 🌤️
homepage: https://openweathermap.org
os: ["darwin", "linux", "win32"]
requires:
  env: ["OPENWEATHER_API_KEY"]
always: false
---

# Weather Skill

Get weather information from OpenWeatherMap.

## Commands

- `weather <city>` - Get current weather
- `forecast <city> <days>` - Get weather forecast

## Dependencies

- `OPENWEATHER_API_KEY` environment variable

## Usage

```
@weather weather London
@weather forecast Tokyo 5
```
