# Urban Campaign Intelligence

Projet vitrine MVP pour démontrer une architecture agentique AWS appliquée à l'allocation contextuelle de campagnes urbaines.

Pour naviguer vite dans le repo :

- [docs/README.md](/home/xclem/projetsperso/agentic-campaign/docs/README.md) : index documentaire
- [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md) : état réel et priorités
- [ARCHITECTURE.md](/home/xclem/projetsperso/agentic-campaign/ARCHITECTURE.md) : architecture cible et patterns agentiques
- [roadmap.md](/home/xclem/projetsperso/agentic-campaign/roadmap.md) : lots et ordre d'exécution

## Objectif

Démontrer en peu de temps une chaîne de bout en bout crédible basée sur :

- AWS Bedrock / AgentCore
- orchestration multi-agents
- placement multi-LLM
- hooks, agents et skills
- scoring déterministe avec explication LLM
- environnement de démo rapide à déployer et réversible

## Périmètre actuel

- 20 zones urbaines à Paris
- 5 annonceurs réalistes
- modèle d'inventaire simplifié
- recommandations uniquement, sans disponibilité réelle des panneaux
- support d'un raisonnement multi-événements simplifié par zone

## État actuel

- moteur MVP local déterministe implémenté
- agents de contexte spécialisés implémentés
- provider Gateway mocké et contrats tools formalisés
- provider météo `Open-Meteo` implémenté avec fallback vers le mock
- provider événements `Paris Open Data` implémenté avec fallback vers le mock
- provider mobilité `hour-of-week forecast` implémenté
- runner CLI local implémenté
- smoke tests implémentés
- influence multi-événements agrégée par zone implémentée
- `deploy.sh` implémenté avec validation AgentCore, bucket S3 durci, manifest et `deploy-outputs.json`
- `destroy.sh` implémenté avec teardown AgentCore/CDK et nettoyage S3 piloté par les outputs de déploiement
- projet AgentCore cible présent sous `agentcore-project/UrbanCampaignIntelligencePoc`
- cible AWS cadrée et partiellement implémentée, mais endpoint `AWS_IAM`, `AgentCore Gateway` et smoke test signé pas encore démontrés de bout en bout

Le suivi détaillé et la prochaine action prioritaire vivent dans [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md).

## Structure du repo

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── Urban_Campaign_Intelligence_PRD_MVP.md
├── roadmap.md
├── agents/
├── data/
├── docs/
├── hooks/
├── outputs/
├── scripts/
├── skills/
├── src/
├── tests/
└── tools/
```

## Stratégie d'exécution

1. Construire d'abord un workflow local déterministe.
2. Ajouter ensuite l'orchestration multi-agents via AgentCore.
3. Ajouter enfin les scripts de déploiement AWS.

## Livrables MVP

- modèle de données pour les zones, annonceurs et scénarios
- contrat `CityContext`
- contrat de scoring déterministe
- structure de sortie prête pour l'explication
- scripts `bootstrap` / `deploy` / `demo` / `destroy`

## Known limitations

- la cible AWS `AgentCore-first` n'est pas encore démontrée de bout en bout
- `AgentCore Gateway` n'est pas encore branché sur le flux final
- le smoke test signé `AWS_IAM` reste à figer sur l'endpoint final
- le harness d'évaluation AWS n'est pas encore branché
- certains schémas anciens dans `docs/diagrams/` sont conservés à titre historique et ne sont plus canoniques

## Documentation canonique

Pour éviter les doublons de lecture :

- `README.md` = vue d'ensemble rapide + commandes utiles
- `docs/STATUS.md` = vérité opérationnelle du moment
- `ARCHITECTURE.md` = vérité architecture / design
- `roadmap.md` = ordre d'exécution
- `docs/DECISIONS.md` = décisions structurantes

Les documents d'audit dans `docs/` servent de synthèse ou de support d'entretien, pas de source principale de vérité.

## Exécution locale

Exécuter un scénario :

```bash
PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Exécuter un scénario avec résumé console + export JSON dans un fichier :

```bash
PYTHONPATH=src python -m urban_campaign_intelligence.runner \
  --scenario fashion_week \
  --summary \
  --output outputs/fashion_week.json
```

Le `summary` console s'appuie sur un `recommended ranking` diversifié pour éviter un top final trop concentré sur une seule marque, tout en conservant le `raw ranking` complet dans le JSON.
Il inclut aussi un `executive_summary` séparé du résumé technique.

## Format des scénarios fake

Les scénarios de [data/scenarios.json](/home/xclem/projetsperso/agentic-campaign/data/scenarios.json) servent maintenant de harness de test explicite. Ils injectent directement :

- `weather`
- `mobility`
- `events` riches avec `title`, `venue`, `description`, `audience_hint`, `raw_tags`
- `calendar`

Exemple simplifié :

```json
{
  "id": "concert_bercy",
  "datetime": "2026-09-18T19:30:00+02:00",
  "city": "Paris",
  "calendar": {
    "day_type": "weekday",
    "school_holiday": false
  },
  "inputs": {
    "weather": {
      "mode": "mock",
      "raw_condition": "clear",
      "temperature_c": 22
    },
    "events": [
      {
        "mode": "mock",
        "event_type": "major_concert",
        "title": "Dua Lipa Live at Accor Arena",
        "venue": "Accor Arena"
      }
    ],
    "mobility": {
      "mode": "mock",
      "network_status": "localized_peak"
    }
  }
}
```

Cela permet de tester facilement des scénarios croisés sans dépendre d'une source externe.

Exécuter un scénario avec météo semi-réelle via `Open-Meteo` :

```bash
WEATHER_PROVIDER=open_meteo PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Exécuter un scénario avec météo et événements semi-réels :

```bash
WEATHER_PROVIDER=open_meteo EVENTS_PROVIDER=paris_open_data PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Exécuter un scénario avec météo, événements et mobilité forecast :

```bash
WEATHER_PROVIDER=open_meteo EVENTS_PROVIDER=paris_open_data MOBILITY_PROVIDER=forecast PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Activer le mode LLM pour `Events Agent` via OpenRouter :

```bash
export AGENTCAMPAIGN_OPENROUTER_API_KEY="..."
export AGENTCAMPAIGN_OPENROUTER_MODEL="deepseek/deepseek-chat"
export EVENTS_AGENT_MODE=llm
PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Activer un vrai workflow multi-LLM simple :

```bash
export AGENTCAMPAIGN_OPENROUTER_API_KEY="..."
export EVENTS_AGENT_MODE=llm
export AGENTCAMPAIGN_OPENROUTER_MODEL="google/gemma-4-26b-a4b-it:free"
export REVIEW_AGENT_MODE=llm
export REVIEW_AGENT_OPENROUTER_MODEL="deepseek/deepseek-v4-flash"
PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --pretty
```

Activer un `executive_summary` rédigé par LLM :

```bash
export AGENTCAMPAIGN_OPENROUTER_API_KEY="..."
export EXECUTIVE_SUMMARY_MODE=llm
export EXECUTIVE_SUMMARY_OPENROUTER_MODEL="deepseek/deepseek-v4-flash"
PYTHONPATH=src python -m urban_campaign_intelligence.runner --scenario fashion_week --summary
```

Variables d'environnement supportées :

- `WEATHER_PROVIDER=mock|open_meteo`
- `EVENTS_PROVIDER=mock|paris_open_data`
- `MOBILITY_PROVIDER=forecast|mock`
- `EVENTS_AGENT_MODE=heuristic|llm`
- `REVIEW_AGENT_MODE=heuristic|llm`
- `EXECUTIVE_SUMMARY_MODE=deterministic|llm`
- `AGENTCAMPAIGN_OPENROUTER_API_KEY`
- `AGENTCAMPAIGN_OPENROUTER_MODEL`
- `REVIEW_AGENT_OPENROUTER_MODEL`
- `EXECUTIVE_SUMMARY_OPENROUTER_MODEL`

Exécuter les smoke tests :

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Exécuter la démo locale complète :

```bash
./scripts/demo.sh
```

Le script de démo écrit un fichier JSON par scénario dans `outputs/demo/` et n'affiche en console qu'un résumé compact.

## Contexte AWS local

Les scripts `bootstrap.sh`, `deploy.sh`, `destroy.sh` et `aws_env.sh` tournent en local, pas dans AWS.

Pour verrouiller le bon compte de démo sans committer de contexte sensible sur le repo distant :

```bash
cp deploy.env.example .env.deploy.local
source scripts/aws_env.sh
```

Le mode strict vérifie ensuite :

- `AWS_PROFILE=aws100demo1`
- `EXPECTED_AWS_ACCOUNT_ID=194031983377`
- `AWS_REGION=us-east-1`

## Scripts infra

Préparer l'environnement local minimal :

```bash
AWS_REGION=eu-west-3 ./scripts/bootstrap.sh
```

Préparer un déploiement AWS en mode non destructif :

```bash
DRY_RUN=1 AWS_REGION=eu-west-3 ./scripts/deploy.sh
```

Préparer un teardown AWS en mode non destructif :

```bash
DRY_RUN=1 AWS_REGION=eu-west-3 ./scripts/destroy.sh
```

Les artefacts de déploiement sont écrits dans `outputs/deploy/`.
Le fichier `deploy-outputs.json` sert de point de reprise pour le teardown et les validations ultérieures.
Le bootstrap vérifie aussi `aws`, `agentcore`, `node`, `npm`, `npx`, la région AWS, l'identité AWS, la structure du projet AgentCore cible et exécute les tests locaux par défaut.

## Hors périmètre

- CI/CD niveau production
- Terraform complet
- UI avancée
- intégration à un inventaire média réel
- authentification complexe

## Prochaines étapes techniques

1. Câbler `AgentCore Gateway` sur les contrats tools déjà stabilisés.
2. Ajouter un smoke test `SigV4` rejouable sur l'endpoint `AWS_IAM`.
3. Connecter le flux cible à Bedrock / AgentCore en live.
4. Ajouter un harness AWS léger puis enrichir l'évaluation métier.
