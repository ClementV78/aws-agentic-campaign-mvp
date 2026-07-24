# Decisions

## ADR-001 - MVP deployment strategy

Decision:

- use Bash + AWS CLI + AgentCore CLI first

Reason:

- faster to deliver
- lower infra overhead
- easier to explain in a short portfolio project

## ADR-002 - Decision logic split

Decision:

- keep scoring deterministic
- use LLMs for explanation, arbitration, and review

Reason:

- more testable
- more explainable
- better portfolio signal for system design maturity

## ADR-003 - Scope reduction

Decision:

- keep the MVP at 20 zones and 5 advertisers

Reason:

- enough diversity for useful tradeoffs
- lower implementation cost
- cleaner demo outputs

## ADR-004 - Local engine before AgentCore wiring

Decision:

- implement a local Python engine before wiring Bedrock / AgentCore

Reason:

- isolate business logic from AWS orchestration concerns
- get a runnable demo faster
- reduce debugging surface under time pressure

## ADR-005 - Multi-event reasoning before real mobility integration

Decision:

- implement simple multi-event zone influence now
- defer real geospatial and temporal event modeling

Reason:

- stronger business credibility for the portfolio
- solves an obvious weakness of single-event reasoning
- keeps the POC reversible and understandable

## ADR-006 - Runtime architecture ("option 2")

Three options were compared for the AgentCore runtime:

| Option | Principle | Readability | Robustness | Portfolio value | Status |
|---|---|---|---|---|---|
| 1. Thin adapter + existing engine | thin runtime delegating almost everything to the existing service | high | high | high | earlier checkpoint, no longer the target |
| 2. Strands business agent + deterministic core | a real runtime agent orchestrating stable business modules | high | medium to high | very high | **retained target** |
| 3. Highly declarative AgentCore | delegate more to configuration and managed building blocks | medium | medium | medium | not retained |

Decision:

- retain **option 2**: an AgentCore Runtime hosting a Strands business agent, with scoring
  and allocation kept deterministic and outside the LLM loop

Reason:

- option 1 makes the runtime a passthrough, which weakens the agentic demonstration
- option 3 hides the business logic in configuration and reduces explainability
- option 2 is the only one that is both genuinely agentic and testable on the critical path

Note:

- "option 2" is used as shorthand across the repo; this ADR is its definition

## ADR-007 - Strands SDK for model access, Bedrock as the provider

Decision:

- the Strands SDK is the default for the agentic layer AND for model access:
  BedrockModel for the Converse transport, Agent.structured_output for structured
  extraction constrained by the Pydantic schemas in llm_schemas.py
- Amazon Bedrock is the target model provider
- OpenRouter stays only as a transitional local fallback and is to be removed
- resolution order is Bedrock, then OpenRouter, then deterministic heuristics
- custom code is written only where the SDK does not cover the need

Reason:

- the point of the project is an agentic architecture on AWS; a non-AWS model
  provider on the critical path contradicts it
- a hand-written boto3 Converse client duplicated what BedrockModel already does,
  including the tool-schema trick used to force structured output
- structured_output validates against Pydantic instead of leaving type checks
  scattered across the call sites
- guardrail_id and guardrail_version are BedrockModel options, so the platform
  controls of the DAT attach at the model call
- the default AWS credential chain means the same code runs locally with a profile
  and inside AgentCore Runtime with the runtime role

What stays custom, and why:

- the Bedrock to OpenRouter to deterministic cascade: the SDK has no notion of a
  non-LLM fallback. This is the only "SDK does not cover it" case today.
- the deterministic core (scoring, allocation, CityContext) is kept out of the SDK
  deliberately, per ADR-002. That is a design decision, not an SDK limitation, and
  the two motives must not be conflated.

Consequence:

- src/ is no longer dependency-free: strands-agents and pydantic are required
- the application still runs without a configured provider, degrading to heuristics

## ADR-008 - Nova Lite for the prompt-mode orchestration agent

Context:

- the prompt mode (ARCHITECTURE §4.1, §12.1) needs a model that reliably drives tool use:
  the agent must read a free-text prompt and emit clean tool calls for get_weather /
  get_events / get_mobility, with a city and an ISO datetime, in one pass
- this is a Bedrock model choice specific to the orchestration agent, distinct from the
  per-role LLM model_id still open in PO-1 (events / review / summary)

Decision:

- use **Amazon Nova Lite** (`amazon.nova-lite-v1:0`) as the default model for the
  orchestration agent in orchestrator.py, overridable via AGENTCAMPAIGN_BEDROCK_MODEL_ID
- **Gemma is rejected** for this role

Reason:

- Nova Lite drives the three tool calls reliably in one shot, with well-formed arguments
- Gemma was tested and gave no reliable tool use: 3-4 retries per run and poor output,
  which breaks the "the LLM decides the tool calls" contract the mode depends on
- Nova Lite is cheap, which matters because this agent runs on every prompt request

Consequence:

- the default is a Bedrock-hosted model, consistent with ADR-007 (Bedrock as the provider)
- the choice is reversible per environment through AGENTCAMPAIGN_BEDROCK_MODEL_ID; the model
  id is not hard-coded into the call sites
- the live integration test (agent -> Bedrock -> tools) costs tokens, so it is skipped
  unless AGENTCAMPAIGN_RUN_LLM_TESTS=1
