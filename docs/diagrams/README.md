# Diagrams

## Objectif

Documenter quels schémas sont **canoniques** et quels schémas sont conservés uniquement à titre **historique**.

La cible actuelle du projet est :

- `API Gateway` + `AWS_IAM`
- `Bedrock AgentCore` (Runtime, Gateway, Memory)
- `Amazon Bedrock` multi-LLM
- `S3` + `CloudWatch Logs`

Elle n'est plus `Lambda-first`.

---

## Schémas canoniques

Générés avec archify (SVG dual-thème, lisibles sur GitHub en light et dark).
Chaque `.archify.svg` a sa source éditable `.archify.json` à côté.

| Schéma | Usage |
|---|---|
| `target-aws-architecture.archify.svg` | architecture AWS cible (services, boundaries, flux) |
| `multi-agent-orchestration.archify.svg` | orchestration multi-agents cible (rôles, claims, arbitrage, review) |
| `request-flow.archify.svg` | séquence d'une requête de recommandation de bout en bout |

Régénération (source JSON → HTML archify → SVG autonome) : modifier le `.archify.json`,
re-rendre avec le renderer archify correspondant, puis ré-extraire le SVG dual-thème.

---

## Schémas historiques conservés

Conservés pour mémoire ou itérations intermédiaires.
Ne plus les utiliser comme source principale pour décrire la cible actuelle :

- `aws-target-architecture.*` (drawio/png/svg — remplacé par `target-aws-architecture.archify.svg`)
- `aws-agentic-workflow.*` (drawio/png/svg — remplacé par `multi-agent-orchestration.archify.svg`)
- `aws-target-architecture-mvp.*`
- `aws-target-architecture-simple.*`
- `aws-target-architecture-layered.*`

Toujours canoniques hors architecture cible :

- `deploy-script-flow.*` — explication du script de déploiement
- `agentcore-deploy-flow.*` — mécanique `agentcore deploy` / CDK

---

## Règle d'usage

- cible AWS actuelle → `target-aws-architecture.archify.svg`
- orchestration multi-agents cible → `multi-agent-orchestration.archify.svg`
- flux d'une requête → `request-flow.archify.svg`
- script de déploiement → `deploy-script-flow.*`
- ne plus référencer les schémas historiques sans préciser explicitement qu'ils sont obsolètes
