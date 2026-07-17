# Status

## Objectif

Suivre l'avancement opérationnel du projet avec un niveau de granularité plus fin que la roadmap.

Règle d'usage :

- `roadmap.md` = vision, lots, ordre d'exécution
- `docs/STATUS.md` = état réel, tâches terminées, tâches en cours, prochains pas

---

## Légende

- `done` : terminé
- `in_progress` : en cours
- `next` : prochaine action prioritaire
- `blocked` : bloqué
- `todo` : non démarré

---

## Snapshot

| Domaine | Statut | Commentaire |
|---|---|---|
| Cadrage produit | `done` | PRD, roadmap et scope MVP stabilisés |
| Documentation architecture | `done` | schémas Mermaid et architecture hybride en place |
| Données MVP | `done` | 20 zones, 5 annonceurs, 8 scénarios |
| Moteur local | `done` | pipeline local exécutable de bout en bout |
| Tests locaux | `done` | smoke tests en place |
| Multi-LLM réel | `done` | workflow multi-LLM validé en exécution réelle via OpenRouter avec fallback conservé |
| Multi-events reasoning | `done` | influence événementielle agrégée par zone implémentée |
| Gateway tools contract | `done` | contrats mockés formalisés et branchés localement |
| Weather semi-real backend | `done` | `Open-Meteo` branché avec fallback mock |
| Events semi-real backend | `done` | Paris Open Data branché avec fallback mock |
| Mobility forecast backend | `done` | forecast déterministe `hour_of_week` branché |
| AgentCore orchestration | `todo` | non démarré |
| Déploiement AWS | `blocked` | déploiement réel tenté sur un compte AWS de démo, bloqué par quota `AWS::BedrockAgentCore::Runtime` (`maxAgents limit exceeded`) |

---

## Avancement détaillé

## 1. Cadrage et documentation

| Élément | Statut | Notes |
|---|---|---|
| `AGENTS.md` | `done` | règles projet, objectif portfolio, contraintes |
| `Urban_Campaign_Intelligence_PRD_MVP.md` | `done` | scope réduit et architecture logique alignée |
| `roadmap.md` | `done` | stratégie d'exécution et lots définis |
| `ARCHITECTURE.md` | `done` | workflow, data model, reasoning, decision split |
| `docs/DECISIONS.md` | `done` | ADRs MVP en place |
| `README.md` | `done` | version française et état réel du repo |

### Prochaine action

- `done` : ajouter une courte section "Known limitations" dans `README.md`
- `done` : ajouter un index documentaire léger pour distinguer docs canoniques, docs de delivery et docs d'audit
- `next` : alléger progressivement `README.md` si la doc AWS détaillée continue de grossir

---

## 2. Données

| Élément | Statut | Notes |
|---|---|---|
| `data/zones.json` | `done` | 20 zones cohérentes et diversifiées |
| `data/advertisers.json` | `done` | 5 annonceurs réalistes et variés |
| `data/scenarios.json` | `done` | scénarios fake explicites et plus riches, dont un scénario multi-events |
| `tools/scoring_weights.json` | `done` | pondérations initiales présentes |
| Backend météo semi-réel | `done` | `Open-Meteo` + fallback mock |
| Backend événements semi-réel | `done` | Paris Open Data + fallback mock |
| Contrats Gateway mockés | `done` | formalisés et versionnés |
| Contrats Gateway externes | `done` | météo et événements branchés, mobilité forecast stabilisé |

### Prochaine action

- `done` : remplacer un premier backend mock par une source semi-réelle tout en gardant le même contrat
- `done` : appliquer le même pattern à `events`
- `done` : appliquer le même pattern à `mobility`

---

## 3. Moteur local

| Composant | Statut | Fichier |
|---|---|---|
| Pre-hook | `done` | `src/urban_campaign_intelligence/pre_hook.py` |
| Weather Agent | `done` | `src/urban_campaign_intelligence/context_agents.py` |
| Events Agent | `done` | `src/urban_campaign_intelligence/context_agents.py` |
| Mobility Agent | `done` | `src/urban_campaign_intelligence/context_agents.py` |
| CityContext Builder | `done` | `src/urban_campaign_intelligence/city_context.py` |
| Zone Analyzer Agent | `done` | `src/urban_campaign_intelligence/scoring.py` |
| Advertiser Matcher Agent | `done` | `src/urban_campaign_intelligence/scoring.py` |
| Campaign Allocator Agent | `done` | `src/urban_campaign_intelligence/scoring.py` |
| Review Agent | `done` | `src/urban_campaign_intelligence/review.py` |
| Executive Summary Agent | `done` | `src/urban_campaign_intelligence/runner.py` |
| CLI runner | `done` | `src/urban_campaign_intelligence/runner.py` |

### Limites actuelles

- tous les agents ne sont pas encore supportés par modèle
- `Events Agent`, `Review Agent` et `Executive Summary` supportent désormais un mode `llm` avec fallback heuristique
- la météo et les événements disposent d'une intégration réseau semi-réelle
- le multi-events reasoning reste volontairement heuristique
- le matching annonceur reste encore trop déterministe sur certains cas concert / sport

### Prochaines actions

- `done` : formaliser les interfaces tools pour découpler collecte et interprétation
- `done` : choisir un premier agent à brancher sur un vrai modèle
- `done` : remplacer le bonus événement binaire par une influence agrégée multi-events par zone
- `done` : tester réellement le workflow multi-LLM avec OpenRouter
- `deferred` : affiner ou confirmer davantage le comportement multi-LLM sur d'autres scénarios
- `done` : améliorer la diversité par annonceur dans l'allocateur

---

## 4. Tests et qualité

| Élément | Statut | Notes |
|---|---|---|
| Smoke tests | `done` | `tests/test_runner.py` |
| Validation JSON | `done` | fichiers JSON chargés avec succès |
| Régression scénarios | `in_progress` | couverture encore faible mais scénario multi-events ajouté |
| Assertions métier détaillées | `done` | assertions clés ajoutées sur luxe, sport, chaleur et départ vacances |
| Harness d'évaluation | `todo` | non démarré |

### Prochaine action

- `next` : ajouter un premier harness d'évaluation léger pour comparer quelques scénarios attendus

---

## 5. Intégration AWS / AgentCore

| Élément | Statut | Notes |
|---|---|---|
| `bootstrap.sh` | `done` | vérifie les prérequis Lot 2 (`aws`, `agentcore`, `node`, région, identité AWS, projet AgentCore cible) et peut exécuter les tests locaux |
| `demo.sh` | `done` | lance les scénarios locaux |
| Cadrage infra MVP | `done` | cible `API Gateway + AWS_IAM + AgentCore + AgentCore Gateway + Bedrock + S3 + CloudWatch` documentée |
| `deploy.sh` | `blocked` | déploiement réel lancé, bootstrap CDK OK, bucket S3 et artefacts OK, échec runtime AgentCore sur quota `maxAgents` du compte AWS |
| `destroy.sh` | `in_progress` | teardown AgentCore/CDK + nettoyage S3 pilotés par `deploy-outputs.json` ou le manifeste |
| AgentCore Gateway | `todo` | non démarré |
| Bedrock model mapping | `todo` | non démarré |
| Hooks AWS réels | `todo` | non démarré |

### Prochaine action

- `done` : cadrer la cible infra MVP du Lot 2
- `done` : implémenter `deploy.sh` sur la cible AWS documentée
- `done` : sécuriser le bucket S3 et réordonner la validation AgentCore dans `deploy.sh`
- `done` : consolider le repo autour d'un seul projet AgentCore cible dédié
- `in_progress` : implémenter `destroy.sh` sur la même base
- `next` : remplacer le `main.py` AgentCore template par un runtime POC minimal branché sur le vrai flux métier local
- `next` : préparer le câblage `AgentCore Gateway` sur les contrats tools déjà stabilisés
- `blocked` : reprendre le déploiement live après augmentation du quota AgentCore / runtime sur le compte AWS de démo

---

## 6. Priorités immédiates

### Now

- attendre le retour AWS sur l'augmentation de quota AgentCore / Bedrock avant de relancer le déploiement live

### Next

- remplacer le `main.py` AgentCore template par un runtime POC minimal crédible
- préparer le câblage `AgentCore Gateway` sur les tools/contrats existants
- ajouter un premier harness d'évaluation léger
- préparer la couche Gateway mockée ou locale pour l'intégration AWS
- observer le comportement `forecast` sur plusieurs scénarios
- préparer le prochain retry de déploiement une fois le quota relevé

### Later

- brancher AgentCore Gateway
- brancher Bedrock
- finaliser le smoke test signé sur l'endpoint `AWS_IAM`

---

## Valeur ajoutée différée

Éléments utiles mais volontairement non implémentés à ce stade :

- géolocalisation réelle des événements avec rayon d'impact calculé
- fenêtres `start/end` exploitées finement au lieu d'une logique par `time_slot`
- source mobilité semi-réelle ou réelle
- vrai système de prévision trafic au-delà du simple profil `hour_of_week`
- passe de `post-review deterministic rebalancing` déclenchée par saturation ou faible diversité
- mémoire inter-run ou comparaison entre scénarios
- observabilité agentique plus riche avec traces structurées
- évaluation métier systématique des recommandations

---

## Définition de "done" par lot

## Lot 1

Considéré comme `done` quand :

- le moteur local couvre tous les scénarios MVP
- les justifications sont cohérentes
- les assertions métier minimales sont en place
- au moins une première intégration LLM a été décidée ou câblée proprement

État courant :

- moteur local : `done`
- justifications cohérentes : `done`
- assertions métier minimales : `done`
- première intégration LLM câblée et testée : `done`
- clôture formelle du lot : `done`

## Lot 2

Considéré comme `done` quand :

- les tools Gateway sont définis
- le workflow AgentCore est câblé
- le déploiement AWS est faisable sans bricolage manuel important

État courant :

- bootstrap CDK réel : `done`
- déploiement live réel : `blocked`
- cause du blocage : quota `AWS::BedrockAgentCore::Runtime` / `maxAgents limit exceeded` sur le compte AWS de démo

---

## Mise à jour

À mettre à jour après chaque changement significatif sur :

- architecture
- moteur local
- contrats tools
- intégration AWS
- tests
