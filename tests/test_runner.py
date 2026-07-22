from __future__ import annotations

import os
import unittest

from urban_campaign_intelligence.app_service import UrbanCampaignApplicationService, run_live_request
from urban_campaign_intelligence.gateway_tools import MobilityForecastProvider
from urban_campaign_intelligence.llm_client import StrandsBedrockClient, get_llm_client
from urban_campaign_intelligence.observability import to_gantt, to_mermaid, to_timeline
from urban_campaign_intelligence.local_agent import CampaignRequest, LocalRequestMapper, UrbanCampaignStrandsAgent
from urban_campaign_intelligence.runner import format_summary, run_scenario
from urban_campaign_intelligence.runtime_app import handle_invocation


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_weather_provider = os.environ.get("WEATHER_PROVIDER")
        self.previous_events_provider = os.environ.get("EVENTS_PROVIDER")
        self.previous_mobility_provider = os.environ.get("MOBILITY_PROVIDER")
        self.previous_events_agent_mode = os.environ.get("EVENTS_AGENT_MODE")
        self.previous_review_agent_mode = os.environ.get("REVIEW_AGENT_MODE")
        self.previous_review_agent_model = os.environ.get("REVIEW_AGENT_OPENROUTER_MODEL")
        self.previous_executive_summary_mode = os.environ.get("EXECUTIVE_SUMMARY_MODE")
        self.previous_executive_summary_model = os.environ.get("EXECUTIVE_SUMMARY_OPENROUTER_MODEL")
        self.previous_openrouter_key = os.environ.get("AGENTCAMPAIGN_OPENROUTER_API_KEY")
        self.previous_openrouter_model = os.environ.get("AGENTCAMPAIGN_OPENROUTER_MODEL")
        os.environ["WEATHER_PROVIDER"] = "mock"
        os.environ["EVENTS_PROVIDER"] = "mock"
        os.environ["MOBILITY_PROVIDER"] = "mock"
        os.environ["EVENTS_AGENT_MODE"] = "heuristic"
        os.environ["REVIEW_AGENT_MODE"] = "heuristic"
        os.environ["EXECUTIVE_SUMMARY_MODE"] = "deterministic"
        os.environ.pop("REVIEW_AGENT_OPENROUTER_MODEL", None)
        os.environ.pop("EXECUTIVE_SUMMARY_OPENROUTER_MODEL", None)
        os.environ.pop("AGENTCAMPAIGN_OPENROUTER_API_KEY", None)
        os.environ.pop("AGENTCAMPAIGN_OPENROUTER_MODEL", None)

    def tearDown(self) -> None:
        if self.previous_weather_provider is None:
            os.environ.pop("WEATHER_PROVIDER", None)
        else:
            os.environ["WEATHER_PROVIDER"] = self.previous_weather_provider
        if self.previous_events_provider is None:
            os.environ.pop("EVENTS_PROVIDER", None)
        else:
            os.environ["EVENTS_PROVIDER"] = self.previous_events_provider
        if self.previous_mobility_provider is None:
            os.environ.pop("MOBILITY_PROVIDER", None)
        else:
            os.environ["MOBILITY_PROVIDER"] = self.previous_mobility_provider
        if self.previous_events_agent_mode is None:
            os.environ.pop("EVENTS_AGENT_MODE", None)
        else:
            os.environ["EVENTS_AGENT_MODE"] = self.previous_events_agent_mode
        if self.previous_review_agent_mode is None:
            os.environ.pop("REVIEW_AGENT_MODE", None)
        else:
            os.environ["REVIEW_AGENT_MODE"] = self.previous_review_agent_mode
        if self.previous_review_agent_model is None:
            os.environ.pop("REVIEW_AGENT_OPENROUTER_MODEL", None)
        else:
            os.environ["REVIEW_AGENT_OPENROUTER_MODEL"] = self.previous_review_agent_model
        if self.previous_executive_summary_mode is None:
            os.environ.pop("EXECUTIVE_SUMMARY_MODE", None)
        else:
            os.environ["EXECUTIVE_SUMMARY_MODE"] = self.previous_executive_summary_mode
        if self.previous_executive_summary_model is None:
            os.environ.pop("EXECUTIVE_SUMMARY_OPENROUTER_MODEL", None)
        else:
            os.environ["EXECUTIVE_SUMMARY_OPENROUTER_MODEL"] = self.previous_executive_summary_model
        if self.previous_openrouter_key is None:
            os.environ.pop("AGENTCAMPAIGN_OPENROUTER_API_KEY", None)
        else:
            os.environ["AGENTCAMPAIGN_OPENROUTER_API_KEY"] = self.previous_openrouter_key
        if self.previous_openrouter_model is None:
            os.environ.pop("AGENTCAMPAIGN_OPENROUTER_MODEL", None)
        else:
            os.environ["AGENTCAMPAIGN_OPENROUTER_MODEL"] = self.previous_openrouter_model

    def test_fashion_week_returns_expected_sections(self) -> None:
        result = run_scenario("fashion_week")

        self.assertIn("city_context", result)
        self.assertIn("allocation_plan", result)
        self.assertIn("review", result)
        self.assertIn("executive_summary", result)
        self.assertIn("execution_log", result)
        self.assertTrue(result["allocation_plan"]["ranked_matches"])
        self.assertTrue(result["allocation_plan"]["recommended_matches"])
        self.assertEqual(result["execution_log"][0]["step"], "pre_hook")
        self.assertTrue(any(entry.get("tool") == "get_weather" for entry in result["execution_log"]))

    def test_transport_strike_adds_warning(self) -> None:
        result = run_scenario("transport_strike")
        warnings = result["review"]["warnings"]
        self.assertTrue(any("confidence" in warning.lower() or "disruption" in warning.lower() for warning in warnings))

    def test_mock_provider_mode_is_exposed_in_log(self) -> None:
        result = run_scenario("concert_bercy")
        weather_tool_entries = [entry for entry in result["execution_log"] if entry.get("tool") == "get_weather"]
        self.assertEqual(weather_tool_entries[0]["details"]["provider_mode"], "scenario_injected")
        events_tool_entries = [entry for entry in result["execution_log"] if entry.get("tool") == "get_events"]
        self.assertEqual(events_tool_entries[0]["details"]["provider_mode"], "scenario_injected")
        mobility_tool_entries = [entry for entry in result["execution_log"] if entry.get("tool") == "get_mobility"]
        self.assertEqual(mobility_tool_entries[0]["details"]["provider_mode"], "scenario_injected")

    def test_events_agent_llm_mode_falls_back_to_heuristic_without_key(self) -> None:
        os.environ["EVENTS_AGENT_MODE"] = "llm"
        result = run_scenario("concert_bercy")
        events_agent_entries = [entry for entry in result["execution_log"] if entry.get("agent") == "events_agent"]
        self.assertNotIn("fallback_count", events_agent_entries[0]["details"])

    def test_review_agent_llm_mode_falls_back_to_heuristic_without_key(self) -> None:
        os.environ["REVIEW_AGENT_MODE"] = "llm"
        result = run_scenario("concert_bercy")
        review_entries = [entry for entry in result["execution_log"] if entry.get("agent") == "review_agent"]
        self.assertEqual(review_entries[0]["details"]["mode"], "heuristic")

    def test_summary_contains_key_sections(self) -> None:
        result = run_scenario("fashion_week")
        summary = format_summary(result)
        self.assertIn("Scenario: fashion_week", summary)
        self.assertIn("Top recommendations:", summary)
        self.assertIn("Executive summary:", summary)
        self.assertIn("Warnings:", summary)

    def test_recommended_matches_are_more_diversified_than_raw_ranking(self) -> None:
        result = run_scenario("fashion_week")
        raw_top_advertisers = [match["advertiser_name"] for match in result["allocation_plan"]["ranked_matches"][:3]]
        recommended_top_advertisers = [match["advertiser_name"] for match in result["allocation_plan"]["recommended_matches"][:3]]
        self.assertEqual(len(set(raw_top_advertisers)), 1)
        self.assertGreater(len(set(recommended_top_advertisers)), 1)

    def test_multi_events_build_zone_level_event_influence(self) -> None:
        result = run_scenario("multi_events_paris")
        event_influence = result["city_context"]["event_influence_by_zone"]
        self.assertIn("avenue_montaigne", event_influence)
        self.assertIn("accor_arena", event_influence)
        self.assertIn("parc_des_princes", event_influence)
        self.assertGreater(event_influence["avenue_montaigne"]["score"], event_influence.get("gare_du_nord", {"score": 0.0})["score"])

    def test_multi_events_do_not_force_fashion_brand_on_station_zone(self) -> None:
        result = run_scenario("multi_events_paris")
        gare_du_nord_match = result["allocation_plan"]["by_zone"]["gare_du_nord"]
        self.assertNotEqual(gare_du_nord_match["advertiser_name"], "Chanel")

    def test_fashion_week_keeps_luxury_brand_on_premium_zone(self) -> None:
        result = run_scenario("fashion_week")
        avenue_montaigne_match = result["allocation_plan"]["by_zone"]["avenue_montaigne"]
        self.assertEqual(avenue_montaigne_match["advertiser_name"], "Chanel")

    def test_football_night_favors_nike_on_parc_des_princes(self) -> None:
        result = run_scenario("football_night_parc_des_princes")
        parc_des_princes_match = result["allocation_plan"]["by_zone"]["parc_des_princes"]
        self.assertEqual(parc_des_princes_match["advertiser_name"], "Nike")

    def test_school_holiday_departure_assigns_travel_or_family_brand_to_station_hubs(self) -> None:
        result = run_scenario("school_holiday_departure")
        gare_de_lyon_match = result["allocation_plan"]["by_zone"]["gare_de_lyon"]
        gare_du_nord_match = result["allocation_plan"]["by_zone"]["gare_du_nord"]
        self.assertIn(gare_de_lyon_match["advertiser_name"], {"OUIGO", "Parc Asterix"})
        self.assertIn(gare_du_nord_match["advertiser_name"], {"OUIGO", "Parc Asterix"})

    def test_heatwave_saturday_favors_coca_cola_on_leisure_zone(self) -> None:
        result = run_scenario("heatwave_saturday")
        la_villette_match = result["allocation_plan"]["by_zone"]["la_villette"]
        self.assertEqual(la_villette_match["advertiser_name"], "Coca-Cola")

    def test_executive_summary_llm_mode_falls_back_to_deterministic_without_key(self) -> None:
        os.environ["EXECUTIVE_SUMMARY_MODE"] = "llm"
        result = run_scenario("concert_bercy")
        self.assertEqual(result["executive_summary"]["mode"], "deterministic")

    def test_live_request_runs_with_paris_fixed_context(self) -> None:
        result = run_live_request("2026-09-18T19:30:00+02:00")
        self.assertEqual(result["scenario"]["mode"], "live")
        self.assertEqual(result["scenario"]["city"], "Paris")
        self.assertTrue(result["allocation_plan"]["recommended_matches"])
        self.assertTrue(any(entry.get("tool") == "get_weather" for entry in result["execution_log"]))

    def test_live_request_rejects_non_paris_city(self) -> None:
        with self.assertRaises(ValueError):
            run_live_request("2026-09-18T19:30:00+02:00", city="Lyon")

    def test_local_request_mapper_builds_scenario_request(self) -> None:
        request = LocalRequestMapper.from_dict({"scenario_id": "fashion_week"})
        self.assertEqual(request.mode, "scenario")
        self.assertEqual(request.scenario_id, "fashion_week")

    def test_local_request_mapper_builds_live_request(self) -> None:
        request = LocalRequestMapper.from_dict({"datetime": "2026-09-18T19:30:00+02:00"})
        self.assertEqual(request.mode, "live")
        self.assertEqual(request.city, "Paris")

    def test_local_agent_handles_scenario_request(self) -> None:
        agent = UrbanCampaignStrandsAgent(app_service=UrbanCampaignApplicationService())
        result = agent.handle_request(CampaignRequest(mode="scenario", scenario_id="concert_bercy"))
        self.assertEqual(result["scenario"]["id"], "concert_bercy")

    def test_local_agent_rejects_invalid_live_request(self) -> None:
        agent = UrbanCampaignStrandsAgent(app_service=UrbanCampaignApplicationService())
        with self.assertRaises(ValueError):
            agent.handle_request(CampaignRequest(mode="live", city="Paris"))

    def test_live_request_does_not_fabricate_events_without_real_source(self) -> None:
        result = run_live_request("2026-02-03T09:00:00+01:00")
        self.assertEqual(result["city_context"]["events"], [])
        self.assertTrue(
            any("No real event source" in warning for warning in result["city_context"]["warnings"]),
        )

    def test_live_request_marks_school_calendar_as_unknown(self) -> None:
        result = run_live_request("2026-08-15T15:00:00+02:00")
        self.assertIsNone(result["city_context"]["time_context"]["school_holiday"])
        self.assertTrue(
            any("School calendar unknown" in warning for warning in result["city_context"]["warnings"]),
        )

    def test_scenario_request_keeps_school_holiday_boolean(self) -> None:
        result = run_scenario("school_holiday_departure")
        self.assertIsInstance(result["city_context"]["time_context"]["school_holiday"], bool)
        self.assertFalse(
            any("School calendar unknown" in warning for warning in result["city_context"]["warnings"]),
        )

    def test_request_mapper_rejects_payload_without_scenario_or_datetime(self) -> None:
        with self.assertRaises(ValueError):
            LocalRequestMapper.from_dict({"city": "Paris"})

    def test_llm_cascade_falls_back_to_null_client_without_any_provider(self) -> None:
        for name in ("AGENTCAMPAIGN_LLM_PROVIDER", "AGENTCAMPAIGN_BEDROCK_MODEL_ID",
                     "AGENTCAMPAIGN_OPENROUTER_API_KEY", "AGENTCAMPAIGN_OPENROUTER_MODEL"):
            os.environ.pop(name, None)
        client = get_llm_client()
        self.assertEqual(client.provider, "none")
        self.assertFalse(client.is_configured())

    def test_llm_cascade_prefers_openrouter_when_bedrock_is_unconfigured(self) -> None:
        os.environ.pop("AGENTCAMPAIGN_LLM_PROVIDER", None)
        os.environ.pop("AGENTCAMPAIGN_BEDROCK_MODEL_ID", None)
        os.environ["AGENTCAMPAIGN_OPENROUTER_API_KEY"] = "test-key"
        os.environ["AGENTCAMPAIGN_OPENROUTER_MODEL"] = "test-model"
        try:
            client = get_llm_client()
            self.assertEqual(client.provider, "openrouter")
        finally:
            os.environ.pop("AGENTCAMPAIGN_OPENROUTER_API_KEY", None)
            os.environ.pop("AGENTCAMPAIGN_OPENROUTER_MODEL", None)

    def test_llm_provider_can_be_forced(self) -> None:
        os.environ["AGENTCAMPAIGN_LLM_PROVIDER"] = "bedrock"
        try:
            self.assertEqual(get_llm_client().provider, "bedrock")
        finally:
            os.environ.pop("AGENTCAMPAIGN_LLM_PROVIDER", None)

    def test_bedrock_client_is_unconfigured_without_model_id(self) -> None:
        self.assertFalse(StrandsBedrockClient(model=None, region_name="us-east-1").is_configured())

    def test_run_carries_a_correlation_id_and_timings(self) -> None:
        result = run_scenario("concert_bercy")
        run = result["run"]
        self.assertTrue(run["run_id"].startswith("run_"))
        self.assertEqual(run["mode"], "scenario")
        self.assertEqual(run["step_count"], len(result["execution_log"]))
        self.assertGreater(run["duration_ms"], 0)
        for entry in result["execution_log"]:
            self.assertEqual(entry["run_id"], run["run_id"])
            self.assertIn("t_ms", entry)
            self.assertIn("elapsed_ms", entry)

    def test_two_runs_get_distinct_correlation_ids(self) -> None:
        self.assertNotEqual(run_scenario("concert_bercy")["run"]["run_id"],
                            run_scenario("concert_bercy")["run"]["run_id"])

    def test_execution_log_renders_as_mermaid_and_timeline(self) -> None:
        result = run_scenario("transport_strike")
        mermaid = to_mermaid(result)
        self.assertTrue(mermaid.startswith("```mermaid\nsequenceDiagram"))
        self.assertTrue(mermaid.endswith("```"))
        self.assertIn("get_weather", mermaid)
        self.assertIn("Note over C:", mermaid)
        self.assertIn("TOTAL", to_timeline(result))

    def test_gantt_places_steps_on_a_non_overlapping_time_axis(self) -> None:
        result = run_scenario("transport_strike")
        gantt = to_gantt(result)
        self.assertTrue(gantt.startswith("```mermaid\ngantt"))
        self.assertIn("dateFormat x", gantt)
        # Sections must be contiguous: a repeated section renders a misplaced label.
        sections = [line.split("section ")[1] for line in gantt.splitlines() if "    section " in line]
        self.assertEqual(len(sections), len(set(sections)))
        previous_end = 0
        for entry in result["execution_log"]:
            self.assertGreaterEqual(entry["start_ms"], previous_end - 1e-6)
            self.assertGreaterEqual(entry["end_ms"], entry["start_ms"])
            previous_end = entry["end_ms"]

    def test_runtime_entrypoint_handles_a_scenario_payload(self) -> None:
        result = handle_invocation({"scenario_id": "concert_bercy"})
        self.assertEqual(result["scenario"]["id"], "concert_bercy")
        self.assertTrue(result["run"]["run_id"].startswith("run_"))
        self.assertTrue(result["allocation_plan"]["recommended_matches"])

    def test_runtime_entrypoint_handles_a_live_payload(self) -> None:
        result = handle_invocation({"datetime": "2026-09-18T19:30:00+02:00"})
        self.assertEqual(result["scenario"]["mode"], "live")
        self.assertEqual(result["scenario"]["city"], "Paris")

    def test_runtime_entrypoint_rejects_empty_payload(self) -> None:
        with self.assertRaises(ValueError):
            handle_invocation({})

    def test_build_app_attaches_the_entrypoint(self) -> None:
        try:
            import bedrock_agentcore  # noqa: F401
        except ImportError:
            self.skipTest("bedrock-agentcore not installed")
        from urban_campaign_intelligence.runtime_app import build_app
        app = build_app()
        self.assertIn("main", app.handlers)

    def test_mobility_forecast_provider_detects_station_peak(self) -> None:
        provider = MobilityForecastProvider()
        summary = provider._forecast_pattern(weekday=2, hour=8)
        self.assertEqual(summary["network_status"], "station_peak")
        self.assertEqual(summary["severity"], "medium")

    def test_mobility_forecast_provider_detects_weekend_dense_central(self) -> None:
        provider = MobilityForecastProvider()
        summary = provider._forecast_pattern(weekday=5, hour=15)
        self.assertEqual(summary["network_status"], "dense_central")


if __name__ == "__main__":
    unittest.main()
