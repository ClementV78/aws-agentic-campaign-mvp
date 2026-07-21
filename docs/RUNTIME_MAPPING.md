# Mapping runtime — composants et frontières

Ce document descend d'un cran sous [../ARCHITECTURE.md](../ARCHITECTURE.md) §5.2 : là où le DAT
décrit des **rôles**, celui-ci mappe les **fichiers et classes réels** du projet sur la frontière
AgentCore / Strands / code métier.

Il répond à une seule question : *pour chaque brique du code, qui la gouverne et où s'exécute-t-elle ?*

| Pour… | Voir |
| --- | --- |
| l'architecture cible et les décisions | [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| l'état d'avancement réel | [STATUS.md](STATUS.md) |
| le choix « option 2 » | [DECISIONS.md](DECISIONS.md) ADR-006 |
| le choix du fournisseur de modèles | [DECISIONS.md](DECISIONS.md) ADR-007 |

## Règle de lecture

Le schéma ci-dessous décrit la **cible**. L'agent y appelle réellement les tools, et les tools y sont
de vraies surfaces gouvernées. Ce n'est pas encore l'état du code — voir [STATUS.md](STATUS.md).

L'accès modèle passe par le **SDK Strands** : `llm_client.StrandsBedrockClient` enveloppe
`BedrockModel` (transport Converse) et `Agent.structured_output` (extraction contrainte par les
schémas Pydantic de `llm_schemas.py`). `OpenRouterClient` reste un repli local transitoire, hors
cible (ADR-007).

## Légende

Blocs :

- **`AgentCore`** : enveloppe runtime et surfaces cloud gouvernées par la plateforme
- **`Strands`** : boucle agentique et orchestration
- **`Custom code`** : logique portée par le code du projet

Couleurs : bleu = `AgentCore`, cyan = `Strands`, vert = code projet, violet pointillé = optionnel.

Scope porté par les labels : `local only`, `shared`, `cloud only`, `optional`.

## Vue intégrée

```mermaid
flowchart LR
    classDef runtime fill:#eef2ff,stroke:#3730a3,color:#1e1b4b,stroke-width:1.5px;
    classDef loop fill:#ecfeff,stroke:#0f766e,color:#134e4a,stroke-width:1.5px;
    classDef code fill:#ecfdf5,stroke:#059669,color:#064e3b,stroke-width:1.5px;
    classDef optional fill:#f5f3ff,stroke:#7c3aed,color:#4c1d95,stroke-width:1.5px,stroke-dasharray: 6 4;

    subgraph AGENTCORE[AgentCore]
      direction TB
      RUNTIME[BedrockAgentCoreApp + main.py<br/>scope: cloud only]:::runtime
      BEDROCK[Bedrock models<br/>scope: cloud only]:::runtime
      MCP[MCPClient / AgentCore Gateway tools<br/>scope: cloud only]:::runtime
      HOOKS[AgentCore hooks envelope<br/>scope: cloud only]:::runtime
      MEMORY[AgentCore Memory<br/>scope: optional]:::optional
    end

    subgraph STRANDS[Strands]
      direction TB
      STRANDSRT[Strands Agent runtime<br/>scope: cloud only]:::loop
      NCM[NullConversationManager<br/>scope: cloud only]:::loop
      SBM[BedrockModel + structured_output<br/>scope: shared]:::loop
    end

    subgraph CUSTOM[Custom code]
      direction TB
      CLI[runner.py CLI<br/>scope: local only]:::code
      LRM[LocalRequestMapper<br/>scope: local only]:::code
      RRM[RuntimeRequestMapper<br/>scope: cloud only]:::code
      CREQ[CampaignRequest<br/>scope: shared]:::code
      UCSA[UrbanCampaignStrandsAgent<br/>scope: shared]:::code
      RSP[RuntimeResponseMapper<br/>scope: cloud only]:::code
      APP[UrbanCampaignApplicationService<br/>scope: shared]:::code
      DATA[DataAccessModule<br/>scope: shared]:::code
      PRE[PreHookModule<br/>scope: shared]:::code
      ENRICH[Context Enrichment<br/>ContextAgents + CityContext<br/>scope: shared]:::code
      DECIDE[Deterministic Decision Engine<br/>Scoring + Allocation<br/>scope: shared]:::code
      OUTPUT[Output Review and Summary<br/>Review + ExecutiveSummary<br/>scope: shared]:::code
      WEATHER[get_weather tool<br/>scope: shared]:::code
      EVENTS[get_events tool<br/>scope: shared]:::code
      MOBILITY[get_mobility tool<br/>scope: shared]:::code
    end

    CLI -. local dev only .-> LRM --> CREQ
    RUNTIME --> RRM --> CREQ
    RUNTIME --> STRANDSRT --> NCM
    STRANDSRT --> UCSA
    CREQ --> UCSA --> APP --> RSP
    RSP --> RUNTIME

    APP --> DATA
    APP --> PRE
    APP --> ENRICH
    APP --> DECIDE
    APP --> OUTPUT

    UCSA --> WEATHER
    UCSA --> EVENTS
    UCSA --> MOBILITY

    ENRICH --> SBM
    OUTPUT --> SBM
    SBM --> BEDROCK

    STRANDSRT -. tool calling via runtime / MCP .-> MCP
    MCP -. backed by governed tools if externalized .-> WEATHER
    MCP -. backed by governed tools if externalized .-> EVENTS
    MCP -. backed by governed tools if externalized .-> MOBILITY

    PRE -. pre-run normalization .-> HOOKS
    OUTPUT -. response guardrails / final checks .-> HOOKS
    UCSA -. optional cross-session recall later .-> MEMORY
```

### Lecture rapide

| Question | Réponse |
| --- | --- |
| Qu'est-ce qui est **local seulement** ? | [runner.py](../src/urban_campaign_intelligence/runner.py), `LocalRequestMapper` |
| Qu'est-ce qui est **partagé** local / cloud ? | `CampaignRequest`, `UrbanCampaignStrandsAgent`, `UrbanCampaignApplicationService`, les 4 blocs métier, la couche providers |
| Qu'apportent **AgentCore et Strands** ? | `BedrockAgentCoreApp + main.py`, `Strands Agent runtime`, **`BedrockModel` + `structured_output`**, les mappers runtime, `MCPClient / Gateway`, `Memory` plus tard |

Le métier reste dans le code du projet. AgentCore apporte l'enveloppe runtime, le tool calling et
les points d'extension cloud. **Strands porte la boucle agentique et l'accès modèle** — depuis la
migration, aucun appel LLM ne part du code projet sans passer par `BedrockModel`. Ce que Strands ne
porte pas : la logique métier critique, et la cascade de repli vers l'heuristique déterministe.

### Détail regroupé dans le schéma

| Bloc du schéma | Composants réels |
| --- | --- |
| `Context Enrichment` | `ContextAgentsModule`, `CityContextModule` |
| accès modèle | `StrandsBedrockClient` → `strands.models.BedrockModel` + `Agent.structured_output` |
| contrats de sortie LLM | `llm_schemas.py` : `EventClassification`, `AllocationReview`, `ExecutiveSummary` |
| `Deterministic Decision Engine` | `ScoringModule`, allocation métier |
| `Output Review and Summary` | `ReviewModule`, `ExecutiveSummaryModule` |
| `get_weather tool` | `MockGatewayProvider`, `OpenMeteoWeatherProvider` |
| `get_events tool` | `GatewayProvider`, `ParisOpenDataEventsProvider` |
| `get_mobility tool` | `GatewayProvider`, `MobilityForecastProvider` |

## Qui contrôle quoi

| Zone | Contrôlé par | Rôle | Observable par défaut | Permissions |
|---|---|---|---|---|
| Runtime entrypoint | AgentCore | recevoir la requête, exécuter le runtime, propager l'identité | oui | IAM du runtime |
| Strands agent loop | Strands | orchestration, choix d'appels, tool calling, prompt | partiellement | héritées du runtime + accès tools |
| Tools externalisés | AgentCore Gateway / MCP | accès gouverné aux sources externes | oui | auth tool par tool |
| Providers inline | code projet | accès direct aux providers Python | seulement si loggué explicitement | permissions du runtime |
| PreHookModule | code projet | validation, normalisation, `time_context` | seulement si loggué explicitement | aucune |
| CityContext / scoring / allocation | code projet | logique métier déterministe | seulement si loggué explicitement | aucune |
| Appels LLM | **Strands `BedrockModel`** sur Bedrock | classification, review, executive summary | oui, côté appels modèle | `bedrock:InvokeModel` |
| Memory | AgentCore Memory | rappel cross-session | oui | droits Memory dédiés |

### Conséquence sur l'observabilité

Ce tableau est ce qui justifie le chapitre 11 du DAT.

**Visible automatiquement** dès qu'on passe par AgentCore / Bedrock / Gateway : entrée runtime,
identité IAM, session et `run_id`, appels modèle, tokens consommés, appels Gateway / MCP, logs runtime.

**Non visible automatiquement** tant que le traitement reste un appel Python interne :
`build_city_context()`, le calcul de scoring, les branches d'allocation, les validations de review.

Une lecture fine du workflow impose donc une **trace applicative structurée** côté projet, en
complément de ce qu'AgentCore fournit. Plus une capacité est externalisée derrière une surface
AgentCore — runtime, appel modèle, tool, memory — plus elle devient observable et gouvernable.

## Cas particulier : `PreHookModule`

`PreHookModule` n'est **pas** un hook natif AgentCore, c'est un pré-traitement métier local.

Son rôle : valider l'entrée, normaliser la datetime, dériver le `time_slot`, construire le
`time_context`, initialiser les métadonnées du pipeline.

Le lien avec AgentCore est conceptuel — il joue la préparation du run — mais il n'est pas gouverné
par la plateforme comme l'est un tool ou un appel modèle.

## Fourni vs à écrire

### Fourni par le squelette AgentCore / Strands

`BedrockAgentCoreApp`, l'entrypoint runtime, `Agent`, `NullConversationManager`, le support MCP / tools.

### Présent dans le projet

[local_agent.py](../src/urban_campaign_intelligence/local_agent.py) ·
[app_service.py](../src/urban_campaign_intelligence/app_service.py) ·
[gateway_tools.py](../src/urban_campaign_intelligence/gateway_tools.py) ·
[context_agents.py](../src/urban_campaign_intelligence/context_agents.py) ·
[pre_hook.py](../src/urban_campaign_intelligence/pre_hook.py) ·
[city_context.py](../src/urban_campaign_intelligence/city_context.py) ·
[scoring.py](../src/urban_campaign_intelligence/scoring.py) ·
[review.py](../src/urban_campaign_intelligence/review.py) ·
[executive_summary.py](../src/urban_campaign_intelligence/executive_summary.py) ·
[data_access.py](../src/urban_campaign_intelligence/data_access.py)

Côté structure : une façade `UrbanCampaignStrandsAgent`, un contrat `CampaignRequest`, un mapper
local `LocalRequestMapper`, une couche service `UrbanCampaignApplicationService`.

### À écrire pour matérialiser la cible

- transformer `UrbanCampaignStrandsAgent` en agent Strands complet
- `RuntimeRequestMapper` et `RuntimeResponseMapper`
- le wiring runtime remplaçant l'agent générique par l'agent métier
- le passage de `get_weather`, `get_events`, `get_mobility` vers de vrais tools gouvernés
- `AgentCore Memory` si un usage concret le justifie

L'ordonnancement de ces chantiers est dans [../ARCHITECTURE.md](../ARCHITECTURE.md) §12.2.
