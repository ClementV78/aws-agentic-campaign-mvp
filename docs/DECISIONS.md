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
