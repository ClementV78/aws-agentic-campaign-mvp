# Packaging — un métier partagé, trois façades

Ce document explique comment le code est structuré depuis le câblage de l'entrypoint canonique
(option A) : un **package métier unique**, importé par la CLI, les tests et le runtime AgentCore.

Voir aussi [ARCHITECTURE.md](../ARCHITECTURE.md) §12.2 (trajectoire) et le point ouvert **PO-7**
(packaging de déploiement).

## 1. Qui contient quoi, qui importe quoi

Le métier vit dans un seul package installable. Les trois façades l'importent — aucune ne le
duplique. `handle_invocation` est la couture entre un transport et le pipeline.

```mermaid
flowchart TB
    PKG["urban_campaign_intelligence<br/>package installable (src/)<br/>invocation · app_service · scoring · observability · …"]

    CLI["runner.py<br/>CLI locale"]
    TESTS["tests/<br/>38 tests"]
    MAIN["agentcore-project/…/app/…/main.py<br/>BedrockAgentCoreApp + @entrypoint<br/>(déployé)"]

    CLI -->|importe| PKG
    TESTS -->|importe| PKG
    MAIN -->|importe| PKG

    classDef pkg fill:#ecfdf5,stroke:#059669,color:#064e3b,stroke-width:2px;
    classDef face fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;
    class PKG pkg;
    class CLI,TESTS,MAIN face;
```

Un seul métier, trois façades. Le doublon local (`runtime_app.py`) a été supprimé : il ne reste
qu'un entrypoint canonique, `main.py`.

## 2. Le flux d'une requête

Identique en local et déployé — c'est le même code.

```mermaid
flowchart TB
    C["client<br/>POST /invocations · scenario_id ou datetime"]
    M["main.py · invoke(payload)"]
    H["handle_invocation(payload)<br/>couture transport ↔ métier"]
    R["LocalRequestMapper.from_dict<br/>→ CampaignRequest"]
    A["UrbanCampaignStrandsAgent.handle_request()"]
    P["pipeline déterministe<br/>pre_hook → CityContext → scoring → review"]
    J["réponse JSON<br/>run · scenario · allocation_plan · execution_log"]

    C --> M --> H --> R --> A --> P --> J

    classDef io fill:#f1f5f9,stroke:#475569,color:#0f172a;
    classDef core fill:#ecfdf5,stroke:#059669,color:#064e3b;
    class C,J io;
    class H,R,A,P core;
```

Sans Bedrock configuré, chaque étage LLM dégrade vers son heuristique : la verticale tourne hors
ligne. La réponse porte son identifiant de corrélation sous `run.run_id`.

## 3. Local vs déploiement — la seule différence

En local, le package est installé dans le venv, donc `main.py` le trouve. Au déploiement, `CodeZip`
ne prend que `codeLocation` (`app/`) : le package doit y entrer autrement. C'est **PO-7**.

```mermaid
flowchart TB
    subgraph LOCAL["LOCAL — fonctionne aujourd'hui"]
        direction TB
        L1["pip install -e ."] --> L2["package présent dans le venv"]
        L2 --> L3["main.py importe le package ✓"]
        L3 --> L4["python main.py → curl → 200"]
    end

    subgraph DEPLOY["DÉPLOIEMENT AWS — PO-7, non résolu"]
        direction TB
        D1["agentcore CodeZip"] --> D2["zippe app/ uniquement"]
        D2 --> D3["src/ hors du zip"]
        D3 --> D4["main.py importe le package ✗ ImportError"]
        D4 --> D5["à régler : copie au build · OU · index privé (CodeArtifact)"]
    end

    classDef ok fill:#ecfdf5,stroke:#059669,color:#064e3b;
    classDef ko fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
    class L1,L2,L3,L4 ok;
    class D1,D2,D3,D4,D5 ko;
```

La path-dependency ne résout pas le déploiement : elle pointe hors de `codeLocation`, que le zip
ignore. La décision (copie au build vs index privé) est reportée au premier déploiement réel, lui-même
bloqué par l'accès Bedrock et le quota `AWS::BedrockAgentCore::Runtime`.
