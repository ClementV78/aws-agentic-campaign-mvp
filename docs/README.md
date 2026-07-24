# Index documentaire

Ce dossier regroupe la documentation d'architecture, opérationnelle et d'archive du projet.

## Une question, un document

| Je veux savoir… | Document |
| --- | --- |
| ce que fait le projet, comment l'exécuter | [../README.md](../README.md) |
| comment le système est conçu et pourquoi | [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| où en est réellement le projet | [STATUS.md](STATUS.md) |
| ce qui reste à faire et dans quel ordre | [../roadmap.md](../roadmap.md) |
| pourquoi telle décision a été prise | [DECISIONS.md](DECISIONS.md) |
| comment déployer sur AWS | [RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md) |
| quelles ressources AWS sont déployées (inventaire) | [DEPLOYED_RESOURCES.md](DEPLOYED_RESOURCES.md) |
| à quel fichier correspond quelle brique | [RUNTIME_MAPPING.md](RUNTIME_MAPPING.md) |

---

## 1. Socle

| Document | Rôle | Statut |
| --- | --- | --- |
| [../README.md](../README.md) | vue d'ensemble, exécution locale | canonique |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | DAT : cible, NFR, sécurité, risques, points ouverts | canonique — v1.0 |
| [STATUS.md](STATUS.md) | état réel du repo, prochaines actions, blocages | canonique — **source unique de l'avancement** |
| [../roadmap.md](../roadmap.md) | lots, livrables, critères de sortie | canonique |
| [DECISIONS.md](DECISIONS.md) | ADRs | canonique — source des décisions |

## 2. Références techniques

| Document | Rôle |
| --- | --- |
| [RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md) | procédures de déploiement AWS / AgentCore, IAM, observabilité |
| [GATEWAY_TOOLS.md](GATEWAY_TOOLS.md) | contrats de tools et pattern providers / fallback |
| [RUNTIME_MAPPING.md](RUNTIME_MAPPING.md) | mapping des composants réels sur la frontière AgentCore / Strands / code |
| [PACKAGING.md](PACKAGING.md) | structure du package partagé, flux d'une requête, local vs déploiement (PO-7) |
| [diagrams/README.md](diagrams/README.md) | inventaire des schémas |

## 3. Archive

Documents conservés pour la traçabilité du raisonnement. **Ils ne font pas foi.**
En cas de contradiction, le socle (§1) l'emporte toujours.

| Document | Nature |
| --- | --- |
| [archive/2026-07-cadrage-prd-mvp.md](archive/2026-07-cadrage-prd-mvp.md) | PRD de cadrage initial, remplacé par le DAT |
| [archive/2026-07-12-audit-global.md](archive/2026-07-12-audit-global.md) | audit ponctuel daté |
| [archive/2026-07-lot2-infra-analyse.md](archive/2026-07-lot2-infra-analyse.md) | analyse ayant instruit les décisions infra du Lot 2 |
| [archive/2026-07-aws-existant-vs-cible.md](archive/2026-07-aws-existant-vs-cible.md) | cadrage visuel existant → cible du Lot 2 |

---

## Règles de tenue

- l'**avancement** ne s'écrit que dans `STATUS.md` — jamais dans `roadmap.md` ni dans un doc d'archive
- les **décisions** ne s'écrivent que dans `DECISIONS.md` et `ARCHITECTURE.md` §13
- un document qui a servi à instruire un choix part en `archive/` une fois le choix acté
- seuls les schémas `*.archify.*` font foi ; `diagrams/legacy/` est historique
- on versionne la **source** (`.archify.json`) et ce qui doit s'afficher sans build (`.archify.svg`) ; pas les rendus régénérables
