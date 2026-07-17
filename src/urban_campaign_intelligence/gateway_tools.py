from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


WEATHER_TOOL_RESPONSES: dict[str, dict[str, Any]] = {
    "hot_weather": {
        "provider": "mock_scenarios",
        "raw_condition": "hot_weather",
        "temperature_c": 32,
        "precipitation_mm": 0.0,
        "wind_kph": 12,
    },
    "clear": {
        "provider": "mock_scenarios",
        "raw_condition": "clear",
        "temperature_c": 24,
        "precipitation_mm": 0.0,
        "wind_kph": 9,
    },
    "cloudy": {
        "provider": "mock_scenarios",
        "raw_condition": "cloudy",
        "temperature_c": 18,
        "precipitation_mm": 0.2,
        "wind_kph": 14,
    },
    "cold": {
        "provider": "mock_scenarios",
        "raw_condition": "cold",
        "temperature_c": 4,
        "precipitation_mm": 0.0,
        "wind_kph": 10,
    },
}

EVENT_TOOL_RESPONSES: dict[str, dict[str, Any]] = {
    "major_concert": {
        "provider": "mock_scenarios",
        "event_type": "major_concert",
        "display_name": "Major Concert",
        "title": "Major Concert",
        "venue": "Accor Arena",
        "description": "A sold-out arena concert with a young and mass-market audience.",
        "zone_ids": ["accor_arena", "gare_de_lyon", "bercy_village"],
        "impact_level": "high",
        "start_local": "19:30",
    },
    "fashion_event": {
        "provider": "mock_scenarios",
        "event_type": "fashion_event",
        "display_name": "Fashion Week Event",
        "title": "Paris Fashion Week",
        "venue": "Multiple premium venues",
        "description": "A premium fashion event attracting luxury shoppers, tourists, and high-income visitors.",
        "zone_ids": ["avenue_montaigne", "saint_germain_des_pres", "champs_elysees", "opera"],
        "impact_level": "high",
        "start_local": "17:00",
    },
    "sports_event": {
        "provider": "mock_scenarios",
        "event_type": "sports_event",
        "display_name": "Major Sports Event",
        "title": "Major Sports Event",
        "venue": "Parc des Princes",
        "description": "A high-energy sports event with strong fan attendance and evening crowd peaks.",
        "zone_ids": ["parc_des_princes", "stade_de_france", "chatelet"],
        "impact_level": "high",
        "start_local": "20:00",
    },
    "family_event": {
        "provider": "mock_scenarios",
        "event_type": "family_event",
        "display_name": "Family Outdoor Event",
        "title": "Family Outdoor Event",
        "venue": "Bois de Vincennes",
        "description": "A family-oriented daytime event with leisure and weekend visitors.",
        "zone_ids": ["vincennes", "la_villette", "gare_de_lyon"],
        "impact_level": "medium",
        "start_local": "14:00",
    },
}

MOBILITY_TOOL_RESPONSES: dict[str, dict[str, Any]] = {
    "normal": {
        "provider": "mock_scenarios",
        "network_status": "normal",
        "severity": "low",
        "affected_zone_ids": [],
    },
    "high_near_bercy": {
        "provider": "mock_scenarios",
        "network_status": "localized_peak",
        "severity": "medium",
        "affected_zone_ids": ["accor_arena", "gare_de_lyon", "bercy_village"],
    },
    "major_transport_disruption": {
        "provider": "mock_scenarios",
        "network_status": "major_disruption",
        "severity": "high",
        "affected_zone_ids": ["gare_du_nord", "gare_de_lyon", "gare_montparnasse", "gare_saint_lazare", "chatelet", "republique"],
    },
    "dense_central": {
        "provider": "mock_scenarios",
        "network_status": "dense_central",
        "severity": "medium",
        "affected_zone_ids": ["opera", "champs_elysees", "boulevard_haussmann", "avenue_montaigne"],
    },
    "station_peak": {
        "provider": "mock_scenarios",
        "network_status": "station_peak",
        "severity": "medium",
        "affected_zone_ids": ["gare_du_nord", "gare_de_lyon", "gare_montparnasse", "gare_saint_lazare"],
    },
}


class MobilityForecastProvider:
    """Simple mobility forecast based on average hour-of-week traffic patterns."""

    CENTRAL_ZONE_IDS = ["opera", "champs_elysees", "boulevard_haussmann", "chatelet", "forum_des_halles"]
    STATION_ZONE_IDS = ["gare_du_nord", "gare_de_lyon", "gare_montparnasse", "gare_saint_lazare"]
    BERCY_ZONE_IDS = ["accor_arena", "gare_de_lyon", "bercy_village"]

    def get_mobility(self, city: str, datetime_iso: str) -> dict[str, Any]:
        target_dt = datetime.fromisoformat(datetime_iso)
        weekday = target_dt.weekday()
        hour = target_dt.hour
        summary = self._forecast_pattern(weekday=weekday, hour=hour)
        return {
            "city": city,
            "datetime": datetime_iso,
            "provider": "hour_of_week_forecast",
            "provider_mode": "forecast",
            **summary,
        }

    def _forecast_pattern(self, weekday: int, hour: int) -> dict[str, Any]:
        if weekday < 5 and 7 <= hour < 10:
            return {
                "network_status": "station_peak",
                "severity": "medium",
                "affected_zone_ids": self.STATION_ZONE_IDS,
                "prediction_confidence": 0.72,
                "prediction_basis": "weekday_morning_commute_average",
            }
        if weekday < 5 and 17 <= hour < 20:
            return {
                "network_status": "dense_central",
                "severity": "medium",
                "affected_zone_ids": sorted(set(self.CENTRAL_ZONE_IDS + ["avenue_montaigne"])),
                "prediction_confidence": 0.74,
                "prediction_basis": "weekday_evening_peak_average",
            }
        if weekday < 5 and 10 <= hour < 16:
            return {
                "network_status": "normal",
                "severity": "low",
                "affected_zone_ids": [],
                "prediction_confidence": 0.68,
                "prediction_basis": "weekday_midday_average",
            }
        if weekday >= 5 and 11 <= hour < 19:
            return {
                "network_status": "dense_central",
                "severity": "medium",
                "affected_zone_ids": self.CENTRAL_ZONE_IDS,
                "prediction_confidence": 0.7,
                "prediction_basis": "weekend_daytime_average",
            }
        return {
            "network_status": "normal",
            "severity": "low",
            "affected_zone_ids": [],
            "prediction_confidence": 0.62,
            "prediction_basis": "baseline_hour_of_week_average",
        }


class MockGatewayProvider:
    """Mock Gateway-compatible provider backed by scenario signals."""

    def get_weather(self, city: str, datetime_iso: str, weather_key: str | None = None, weather_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if weather_input:
            response = {
                "provider": "mock_scenarios",
                "raw_condition": weather_input.get("raw_condition", weather_key or "clear"),
                "temperature_c": weather_input.get("temperature_c", 20),
                "precipitation_mm": weather_input.get("precipitation_mm", 0.0),
                "wind_kph": weather_input.get("wind_kph", 10),
            }
        else:
            response = WEATHER_TOOL_RESPONSES.get(
                weather_key or "clear",
                {
                    "provider": "mock_scenarios",
                    "raw_condition": weather_key or "clear",
                    "temperature_c": 20,
                    "precipitation_mm": 0.0,
                    "wind_kph": 10,
                },
            )
        return {"city": city, "datetime": datetime_iso, **response}

    def get_events(self, city: str, datetime_iso: str, event_types: list[str] | None = None, event_inputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        events = []
        if event_inputs:
            for raw_event in event_inputs:
                event_type = raw_event.get("event_type", "generic_event")
                event = {
                    **EVENT_TOOL_RESPONSES.get(
                        event_type,
                        {
                            "provider": "mock_scenarios",
                            "event_type": event_type,
                            "display_name": raw_event.get("title", event_type.replace("_", " ").title()),
                            "zone_ids": [],
                            "impact_level": "medium",
                            "start_local": None,
                        },
                    ),
                    **raw_event,
                    "provider": "mock_scenarios",
                    "display_name": raw_event.get("title") or raw_event.get("display_name") or event_type.replace("_", " ").title(),
                }
                events.append(event)
        else:
            for event_type in event_types or []:
                event = EVENT_TOOL_RESPONSES.get(
                    event_type,
                    {
                        "provider": "mock_scenarios",
                        "event_type": event_type,
                        "display_name": event_type.replace("_", " ").title(),
                        "zone_ids": [],
                        "impact_level": "medium",
                        "start_local": None,
                    },
                )
                events.append(event)
        return {"city": city, "datetime": datetime_iso, "events": events}

    def get_mobility(self, city: str, datetime_iso: str, mobility_key: str | None = None, mobility_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if mobility_input:
            response = {
                "provider": "mock_scenarios",
                "network_status": mobility_input.get("network_status", mobility_key or "normal"),
                "severity": mobility_input.get("severity", "low"),
                "affected_zone_ids": mobility_input.get("affected_zone_ids", []),
                **({"prediction_confidence": mobility_input["prediction_confidence"]} if "prediction_confidence" in mobility_input else {}),
                **({"prediction_basis": mobility_input["prediction_basis"]} if "prediction_basis" in mobility_input else {}),
            }
        else:
            response = MOBILITY_TOOL_RESPONSES.get(
                mobility_key or "normal",
                {
                    "provider": "mock_scenarios",
                    "network_status": mobility_key or "normal",
                    "severity": "low",
                    "affected_zone_ids": [],
                },
            )
        return {"city": city, "datetime": datetime_iso, **response}


class OpenMeteoWeatherProvider:
    """Semi-real weather provider using Open-Meteo geocoding and weather APIs."""

    GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_BASE_URL = "https://api.open-meteo.com/v1/forecast"
    HISTORICAL_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def get_weather(self, city: str, datetime_iso: str) -> dict[str, Any]:
        target_dt = datetime.fromisoformat(datetime_iso)
        latitude, longitude = self._resolve_city(city)
        source_mode = self._select_source_mode(target_dt)
        weather_data = self._fetch_weather(latitude, longitude, target_dt, source_mode)
        return {
            "city": city,
            "datetime": datetime_iso,
            "provider": "open_meteo",
            "provider_mode": source_mode,
            "raw_condition": weather_data["condition"],
            "temperature_c": weather_data["temperature_c"],
            "precipitation_mm": weather_data["precipitation_mm"],
            "wind_kph": weather_data["wind_kph"],
        }

    def _resolve_city(self, city: str) -> tuple[float, float]:
        payload = self._fetch_json(
            self.GEOCODING_BASE_URL,
            {"name": city, "count": 1, "language": "en", "format": "json"},
        )
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"Open-Meteo geocoding returned no result for city '{city}'.")
        return float(results[0]["latitude"]), float(results[0]["longitude"])

    def _select_source_mode(self, target_dt: datetime) -> str:
        now = datetime.now(target_dt.tzinfo)
        delta_days = (target_dt.date() - now.date()).days
        if delta_days <= 0:
            return "historical"
        if delta_days <= 16:
            return "forecast"
        return "historical_analog"

    def _fetch_weather(self, latitude: float, longitude: float, target_dt: datetime, source_mode: str) -> dict[str, Any]:
        query_dt = target_dt
        base_url = self.FORECAST_BASE_URL
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "auto",
            "hourly": "temperature_2m,precipitation,wind_speed_10m,weather_code",
        }

        if source_mode == "historical":
            base_url = self.HISTORICAL_BASE_URL
            params["start_date"] = target_dt.date().isoformat()
            params["end_date"] = target_dt.date().isoformat()
        elif source_mode == "forecast":
            params["start_date"] = target_dt.date().isoformat()
            params["end_date"] = target_dt.date().isoformat()
            params["forecast_days"] = 1
        else:
            base_url = self.HISTORICAL_BASE_URL
            query_dt = target_dt.replace(year=target_dt.year - 1)
            params["start_date"] = query_dt.date().isoformat()
            params["end_date"] = query_dt.date().isoformat()

        payload = self._fetch_json(base_url, params)
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            raise ValueError("Open-Meteo hourly response is empty.")

        target_hour = query_dt.replace(minute=0, second=0, microsecond=0).isoformat()
        try:
            index = times.index(target_hour)
        except ValueError:
            index = 0

        weather_code = int(hourly.get("weather_code", [0])[index])
        return {
            "condition": self._map_weather_code(weather_code),
            "temperature_c": float(hourly.get("temperature_2m", [20.0])[index]),
            "precipitation_mm": float(hourly.get("precipitation", [0.0])[index]),
            "wind_kph": float(hourly.get("wind_speed_10m", [10.0])[index]),
        }

    def _fetch_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"Open-Meteo request failed: {exc}") from exc

    @staticmethod
    def _map_weather_code(weather_code: int) -> str:
        if weather_code in {0, 1}:
            return "clear"
        if weather_code in {2, 3, 45, 48}:
            return "cloudy"
        if weather_code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
            return "rain"
        if weather_code in {71, 73, 75, 77, 85, 86}:
            return "snow"
        if weather_code in {95, 96, 99}:
            return "storm"
        return "cloudy"


class ParisOpenDataEventsProvider:
    """Semi-real events provider backed by Paris Open Data."""

    EVENTS_BASE_URL = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/que-faire-a-paris-/records"
    EVENT_QUERY_MAP: dict[str, list[str]] = {
        "major_concert": ["concert", "musique live", "spectacle musical"],
        "fashion_event": ["mode", "fashion", "création"],
        "sports_event": ["sport", "football", "rugby"],
        "family_event": ["famille", "enfants", "plein air"],
    }

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def get_events(self, city: str, datetime_iso: str, event_types: list[str]) -> dict[str, Any]:
        records = []
        for event_type in event_types:
            query_terms = self.EVENT_QUERY_MAP.get(event_type, [event_type.replace("_", " ")])
            record = self._fetch_best_match(city=city, event_type=event_type, query_terms=query_terms)
            if record is not None:
                records.append(record)
        return {"city": city, "datetime": datetime_iso, "events": records}

    def _fetch_best_match(self, city: str, event_type: str, query_terms: list[str]) -> dict[str, Any] | None:
        for query_term in query_terms:
            payload = self._fetch_json(
                self.EVENTS_BASE_URL,
                {
                    "limit": 3,
                    "where": f'search(title, "{query_term}") OR search(description, "{query_term}")',
                },
            )
            results = payload.get("results", [])
            for record in results:
                if record.get("address_city") in {None, "", "Paris", "Grand Paris"}:
                    return {
                        "provider": "paris_open_data",
                        "event_type": event_type,
                        "display_name": record.get("title") or record.get("title_event") or query_term.title(),
                        "zone_ids": [],
                        "impact_level": "high" if event_type in {"major_concert", "fashion_event"} else "medium",
                        "start_local": record.get("date_start"),
                        "source_url": record.get("url"),
                        "address_name": record.get("address_name"),
                        "address_city": record.get("address_city"),
                        "qfap_tags": record.get("qfap_tags"),
                    }
        return None

    def _fetch_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"Paris Open Data request failed: {exc}") from exc


class GatewayProvider:
    """Composite provider with configurable weather backend and mock fallbacks."""

    def __init__(
        self,
        weather_provider_mode: str | None = None,
        events_provider_mode: str | None = None,
        mobility_provider_mode: str | None = None,
    ) -> None:
        self.weather_provider_mode = (weather_provider_mode or os.getenv("WEATHER_PROVIDER", "mock")).strip().lower()
        self.events_provider_mode = (events_provider_mode or os.getenv("EVENTS_PROVIDER", "mock")).strip().lower()
        self.mobility_provider_mode = (mobility_provider_mode or os.getenv("MOBILITY_PROVIDER", "forecast")).strip().lower()
        self.mock_provider = MockGatewayProvider()
        self.open_meteo_provider = OpenMeteoWeatherProvider()
        self.paris_events_provider = ParisOpenDataEventsProvider()
        self.mobility_forecast_provider = MobilityForecastProvider()

    def get_weather(self, city: str, datetime_iso: str, weather_key: str | None = None, weather_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.weather_provider_mode == "open_meteo":
            try:
                return self.open_meteo_provider.get_weather(city=city, datetime_iso=datetime_iso)
            except ValueError:
                fallback = self.mock_provider.get_weather(city=city, datetime_iso=datetime_iso, weather_key=weather_key, weather_input=weather_input)
                fallback["provider_fallback"] = "mock_scenarios"
                fallback["provider_mode"] = "mock_fallback"
                return fallback
        fallback = self.mock_provider.get_weather(city=city, datetime_iso=datetime_iso, weather_key=weather_key, weather_input=weather_input)
        fallback["provider_mode"] = "mock"
        return fallback

    def get_events(self, city: str, datetime_iso: str, event_types: list[str] | None = None, event_inputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if self.events_provider_mode == "paris_open_data":
            try:
                provider_event_types = event_types or [event.get("event_type", "generic_event") for event in event_inputs or []]
                payload = self.paris_events_provider.get_events(city=city, datetime_iso=datetime_iso, event_types=provider_event_types)
                if payload["events"]:
                    return payload
            except ValueError:
                pass
            fallback = self.mock_provider.get_events(city=city, datetime_iso=datetime_iso, event_types=event_types, event_inputs=event_inputs)
            fallback["provider_fallback"] = "mock_scenarios"
            fallback["provider_mode"] = "mock_fallback"
            return fallback
        payload = self.mock_provider.get_events(city=city, datetime_iso=datetime_iso, event_types=event_types, event_inputs=event_inputs)
        payload["provider_mode"] = "mock"
        return payload

    def get_mobility(self, city: str, datetime_iso: str, mobility_key: str | None = None, mobility_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mobility_provider_mode == "forecast":
            return self.mobility_forecast_provider.get_mobility(city=city, datetime_iso=datetime_iso)
        fallback = self.mock_provider.get_mobility(city=city, datetime_iso=datetime_iso, mobility_key=mobility_key, mobility_input=mobility_input)
        fallback["provider_mode"] = "mock"
        return fallback
