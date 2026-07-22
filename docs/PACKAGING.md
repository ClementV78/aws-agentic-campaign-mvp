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

## 3. Local vs déploiement — le même code, deux façons de le placer

La règle AWS est simple : **tout le code déployé finit dans le zip**, décompressé sous `/var/task`,
premier répertoire du `sys.path`
([doc officielle](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html)).
Il n'existe pas de « path-dependency » vue par le runtime : le conteneur ne voit que le paquet.

En local, `pip install -e .` met le package dans le venv → `main.py` le trouve. Pour le déploiement,
on **copie** le package dans le paquet au moment du build, avec la commande officielle `uv pip
install --target` — mécanisme standard, pas un contournement.

```mermaid
flowchart TB
    subgraph LOCAL["LOCAL — fonctionne aujourd'hui"]
        direction TB
        L1["pip install -e ."] --> L2["package présent dans le venv"]
        L2 --> L3["main.py importe le package ✓"]
        L3 --> L4["python main.py → curl → 200"]
    end

    subgraph DEPLOY["DÉPLOIEMENT AWS — build local, puis zip"]
        direction TB
        D1["uv pip install --target=deployment_package .<br/>(machine locale, repo présent, cible ARM64)"]
        D2["package + deps COPIÉS dans deployment_package/"]
        D3["zip du deployment_package + main.py"]
        D4["/var/task : main.py importe le package ✓"]
        D1 --> D2 --> D3 --> D4
    end

    classDef ok fill:#ecfdf5,stroke:#059669,color:#064e3b;
    class L1,L2,L3,L4,D1,D2,D3,D4 ok;
```

Le point clé : la référence au package est résolue **au build** (localement, où tout le repo est là),
puis **copiée**. Au runtime il ne reste qu'une copie dans le zip — aucune dépendance externe à résoudre.

## 4. Faire entrer le package dans le zip (PO-7)

Procédure de référence, à câbler dans le script de déploiement au déblocage AWS :

```bash
# 1. installer le package + ses deps pour la cible ARM64 du runtime, dans un dossier
uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.13 \
  --target=deployment_package \
  --only-binary=:all: \
  .

# 2. ajouter l'entrypoint, puis zipper
cp agentcore-project/.../app/.../main.py deployment_package/
cd deployment_package && zip -r ../deployment_package.zip .
```

Deux points de vigilance :

- **ARM64 obligatoire** : le runtime AgentCore tourne en `aarch64`. Des wheels `x86_64` échouent au
  déploiement. Nos deps (`strands-agents`, `pydantic`, `boto3`) sont pures Python ou ont des wheels
  ARM64, donc OK — mais toute future dépendance native devra être buildée pour ARM64.
- **Pas de `__pycache__`** dans le paquet (bytecode compilé sur une autre archi, incompatible).

Cette étape est **testable seulement au déblocage** (accès Bedrock + quota
`AWS::BedrockAgentCore::Runtime`). Voir ARCHITECTURE.md §15 (PO-7).

> Note d'organisation : ce document pourra à terme être résorbé, la procédure §4 rejoignant
> [RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md) et les schémas §1–2 restant le support d'explication.
