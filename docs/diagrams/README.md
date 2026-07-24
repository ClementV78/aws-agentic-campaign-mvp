# Diagrams

## Objectif

Documenter quels schémas sont **canoniques** et quels schémas sont conservés uniquement à titre **historique**.

La cible actuelle du projet est :

- `InvokeAgentRuntime` comme entrée principale
- `Bedrock AgentCore` (`Runtime` + `Gateway`, `Memory` optionnelle)
- `Amazon Bedrock` multi-LLM
- `S3` + `CloudWatch Logs`
- `Policy + Bedrock Guardrails` sur la surface tools via Gateway

Elle n'est plus `API Gateway-first`, et elle ne fige pas `Lambda` comme unique backend de tools.

---

## Schémas canoniques

Générés avec archify (SVG dual-thème, lisibles sur GitHub en light et dark).
Chaque diagramme a :

- une source éditable `.archify.json` — **versionnée**
- un SVG statique `.archify.svg` pour les inclusions Markdown — **versionné**
- un rendu interactif `.archify.html` — **non versionné**, régénérable localement depuis le `.json`

| Schéma | Usage |
|---|---|
| `target-aws-architecture.archify.svg` | architecture AWS cible (services, boundaries, flux) |
| `multi-agent-orchestration.archify.svg` | orchestration multi-agents cible (rôles, claims, arbitrage, review) |
| `request-flow.archify.svg` | séquence d'une requête de recommandation de bout en bout |
| `agentcore-capability-map.archify.svg` | carte des capacités AgentCore (calquée sur AWS) avec notre usage et son statut — référencée par `ARCHITECTURE.md` §6 |
| `deployed-request.archify.svg` | séquence d'un run réel sur le runtime déployé : `InvokeAgentRuntime` → agent Nova Lite → tools → pipeline déterministe → reco — `RUNTIME_MAPPING.md` |
| `observability-layers.archify.svg` | les 2 couches d'observabilité (trace GenAI AWS vs `RunTrace`) et leur corrélation par `trace_id`/`session_id` — `RUNTIME_MAPPING.md` |

Régénération : modifier le `.archify.json`, re-rendre le `.archify.html` avec le renderer archify,
puis ré-extraire / régénérer le `.archify.svg` statique pour les docs Markdown.

**Exception — `agentcore-capability-map`** : ce schéma est *hand-placed* (grille de capacités + overlay
statut par couleur, hors modes typés du renderer). Il n'a donc **pas** de `.archify.json` ; c'est le
`.archify.html` qui fait office de **source éditable versionnée**, et le `.archify.svg` (dual-thème) en
est extrait pour les inclusions Markdown. Statut des cases : vert = utilisé, ambre = partiel/câblé local,
rose = cible, gris = non utilisé/différé.

---

## Schémas historiques — `legacy/`

Conservés pour mémoire ou itérations intermédiaires. **Ne pas les utiliser pour décrire la cible.**

| Schéma | Statut |
| --- | --- |
| `legacy/aws-target-architecture.*` | remplacé par `target-aws-architecture.archify.svg` |
| `legacy/aws-target-architecture-mvp.*` | itération intermédiaire |
| `legacy/aws-target-architecture-simple.*` | itération intermédiaire |
| `legacy/aws-target-architecture-layered.*` | itération intermédiaire |
| `legacy/aws-agentic-workflow.*` | remplacé par `multi-agent-orchestration.archify.svg` |
| `legacy/deploy-script-flow.*` | mécanique du script de déploiement, non régénéré |
| `legacy/agentcore-deploy-flow.*` | mécanique `agentcore deploy` / CDK, non régénéré |

---

## Règle d'usage

- cible AWS actuelle → `target-aws-architecture.archify.svg`
- orchestration multi-agents cible → `multi-agent-orchestration.archify.svg`
- flux d'une requête → `request-flow.archify.svg`
- déploiement → texte de [../RUNBOOK_DEPLOY.md](../RUNBOOK_DEPLOY.md) ; les schémas `legacy/` associés ne sont plus tenus à jour
- ne jamais référencer un schéma `legacy/` sans préciser qu'il est historique
