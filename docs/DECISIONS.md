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
