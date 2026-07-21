# Roadmap

## Objectif

Transformer le PRD MVP de **Urban Campaign Intelligence** en un plan d'exécution simple, démontrable rapidement, puis extensible vers une version plus industrialisée.

Cette roadmap privilégie :

- la démonstration rapide de l'orchestration multi-agents
- la simplicité de déploiement
- l'explicabilité des recommandations
- la limitation du périmètre pour éviter un faux MVP

---

## Faits, hypothèses, incertitudes

### Faits

- Le MVP a été pensé au départ comme un POC **montable très rapidement**, avec une ambition initiale de **1 à 2 jours**.
- Le socle cible est **AWS Bedrock AgentCore** avec **Gateway**, **hooks**, **skills** et **multi-agents**.
- Le dépôt doit privilégier **Bash + AWS CLI + AgentCore CLI** pour le déploiement initial.
- Le système raisonne sur un **inventaire simplifié** de **20 zones parisiennes** et **5 annonceurs**.

### Hypothèses

- Le but principal du MVP est une **démo architecture + orchestration**, pas une optimisation média réaliste.
- Les données météo, événements et mobilité peuvent être **mockées ou semi-statiques** si l'intégration réelle ralentit le POC.
- Un seul environnement AWS de démonstration suffit pour la première itération.

### Incertitudes

- Le niveau exact de maturité souhaité pour les intégrations externes n'est pas encore explicite.
- Le niveau de détail attendu pour les rapports de sortie n'est pas encore figé.
- Le choix précis des modèles Bedrock n'est pas documenté dans le PRD.

Note de lecture :

- l'ambition "1 à 2 jours" doit être lue comme un objectif initial de cadrage rapide, pas comme une mesure stricte de l'effort réellement investi dans le repo actuel

---

## Principes d'exécution

1. Construire d'abord une **chaîne démontrable de bout en bout**.
2. Remplacer ensuite les mocks les plus critiques par de vraies intégrations.
3. N'industrialiser qu'après stabilisation du workflow métier et agentique.

Critères de décision :

- `security` : pas de permissions IAM larges sans justification
- `maintainability` : scripts lisibles, structure de repo simple
- `observability` : logs d'orchestration et sorties compréhensibles
- `reversibility` : `destroy.sh` et faible dette infra
- `cost` : minimiser les composants AWS annexes

---

## Vue d'ensemble

| Lot | Période cible | But | Sortie attendue |
|---|---|---|---|
| Lot 0 | Jour 0 | Cadrage et squelette | Repo prêt à implémenter |
| Lot 1 | Jour 1 | Workflow MVP bout en bout | Démo locale/CLI cohérente |
| Lot 2 | Jour 1-2 | Déploiement AWS rapide | POC déployable en <15 min |
| Lot 3 | Jour 2 | Qualité et robustesse | Harness + guardrails minimum |
| Lot 4 | Après MVP | Industrialisation | Base pour itérations sérieuses |

## Statut

L'état d'avancement n'est pas suivi dans ce document.

Source de vérité unique : [docs/STATUS.md](docs/STATUS.md)

---

## Lot 0 - Cadrage et squelette du repo

### Objectif

Poser une structure propre pour éviter de mélanger logique métier, orchestration, données de démo et scripts d'infrastructure.

### Livrables

- arborescence initiale du dépôt
- `README.md`
- `ARCHITECTURE.md`
- dossiers `data/`, `src/`, `tools/`, `tests/`, `scripts/`, `docs/`
- jeu de données statique minimal :
  - zones
  - annonceurs
  - scénarios de test

### Critères de sortie

- un nouveau contributeur comprend le flux global en moins de 10 minutes
- les données métier de base sont versionnées et lisibles
- le périmètre MVP et le hors périmètre sont explicites

### Risques

- partir trop tôt sur une structure "future-proof" inutilement complexe
- surdocumenter avant d'avoir un flux exécutable

---

## Lot 1 - Moteur métier MVP et orchestration locale

### Objectif

Valider la logique fonctionnelle avant d'ajouter la complexité AWS.

### Sous-lots

#### 1.1 Pré-hook et `CityContext`

Livrer :

- normalisation de l'entrée
- calcul du `TimeContext`
- construction d'un `CityContext` unifié

Le `CityContext` doit inclure au minimum :

- météo
- événements
- mobilité
- calendrier / type de journée
- signaux de contexte utiles au scoring

#### 1.2 Agents métier MVP

Livrer une version simple de :

- `Weather Agent`
- `Events Agent`
- `Mobility Agent`
- `Zone Analyzer Agent`
- `Advertiser Matcher Agent`
- `Campaign Allocation Agent`
- `Review Agent`

Garder en parallèle des sources simples :

- `Zones Repository`
- `Advertisers Repository`

Approche recommandée :

- règles simples et déterministes pour le scoring de base
- petits modèles pour agents de contexte
- modèle plus fort pour arbitrage, review et synthèse si nécessaire

#### 1.3 Scoring et allocation

Implémenter :

- score par couple `zone x advertiser`
- pondérations explicites
- exclusions
- pénalité de risque
- allocation finale simple mais cohérente

#### 1.4 Sorties de démonstration

Produire :

- contexte synthétique
- planning par annonceur
- planning par zone
- justification
- score
- confiance
- journal d'orchestration

### Critères de sortie

- un scénario textuel complet produit une recommandation exploitable
- les justifications sont cohérentes avec les signaux d'entrée
- aucune sortie ne prétend utiliser un inventaire publicitaire réel

### État courant

Voir [docs/STATUS.md](docs/STATUS.md).

### Risques

- laisser le LLM faire le scoring principal, ce qui rend le résultat peu contrôlable
- construire des agents trop fins trop tôt, avec surcoût d'orchestration

---

## Lot 2 - Déploiement AWS / AgentCore rapide

### Objectif

Passer d'un workflow local crédible à un POC déployable rapidement sur AWS.

### Livrables

- `scripts/bootstrap.sh`
- `scripts/deploy.sh`
- `scripts/demo.sh`
- `scripts/destroy.sh`
- rôles IAM minimaux
- configuration Bedrock / AgentCore / Gateway
- packaging des hooks, agents, tools et skills

### Ordre recommandé

1. `bootstrap.sh`
2. `deploy.sh`
3. `demo.sh`
4. `destroy.sh`

### Critères de sortie

- déploiement complet en moins de 15 minutes sur un compte AWS dédié
- démonstration exécutable sans manipulation manuelle complexe
- nettoyage possible sans ressources orphelines évidentes

### Risques

- IAM trop permissif pour gagner du temps
- dépendance à des commandes CLI non stabilisées ou sensibles aux versions
- couplage fort entre scripts et environnement local du poste

### Garde-fous

- épingler les prérequis documentés
- journaliser clairement les ressources créées
- centraliser les variables d'environnement

---

## Lot 3 - Qualité, guardrails et harness de test

### Objectif

Rendre la démo robuste, répétable et défendable.

### Livrables

- scénarios automatisés :
  - canicule
  - pluie
  - concert
  - grève
  - fashion week
  - week-end
- validation automatique :
  - cohérence
  - justification
  - confiance
  - diversité
  - comportement multi-events
- guardrails minimum :
  - pas d'inventaire réel
  - allocation indicative
  - confidence obligatoire
  - avertissements si données incomplètes

### Critères de sortie

- les scénarios clés passent sans correction manuelle
- les hallucinations évidentes sont détectées ou limitées
- les sorties exposent clairement leurs limites

### Risques

- tests trop qualitatifs et difficiles à rejouer
- métriques de confiance non définies donc peu crédibles

---

## Lot 4 - Industrialisation post-MVP

### Objectif

Préparer une trajectoire sérieuse sans contaminer le MVP avec des sujets trop lourds.

### Pistes prioritaires

- Terraform ou OpenTofu léger puis complet
- CI/CD
- gestion multi-environnements
- observabilité centralisée
- sécurité IAM durcie
- intégrations réelles météo / mobilité / événements
- UI de visualisation
- cartographie
- évaluation systématique des sorties agents

### Critères d'entrée

Ne démarrer ce lot que si :

- le workflow métier est jugé utile
- la structure agentique est stabilisée
- les coûts d'orchestration sont compris

---

## Backlog priorisé

### P0

- structurer le repo
- définir les jeux de données MVP
- implémenter `CityContext`
- implémenter scoring déterministe
- produire planning + justification + confiance
- fournir scripts `bootstrap/deploy/demo/destroy`

### P1

- brancher AgentCore et Gateway
- ajouter `Review Agent`
- ajouter harness de scénarios
- ajouter logs d'orchestration exploitables
- durcir `deploy.sh` avec validation amont, bucket S3 sécurisé, et preuve de déploiement exploitable

### P2

- intégrer de vraies sources externes
- enrichir le modèle d'allocation
- améliorer les guardrails
- préparer l'industrialisation infra

---

## Backlog à valeur ajoutée

À ne pas implémenter tout de suite, mais à conserver explicitement :

- géolocalisation réelle des événements et rayon d'impact calculé
- temporalité fine avec fenêtres `start/end` réelles
- backend mobilité semi-réel ou réel
- vrai système de prévision trafic au-delà du simple profil `hour_of_week`
- `post-review deterministic rebalancing pass` avec un seul retry et `raw ranking` immuable
- observabilité agentique avancée et traces structurées
- évaluation métier systématique des scénarios

---

## Dépendances clés

### Techniques

- AWS CLI
- AgentCore CLI
- compte AWS dédié
- accès Bedrock dans la région choisie

### Produit / conception

- format exact du `CityContext`
- pondérations initiales du scoring
- format de restitution attendu pour la démo

---

## Jalons recommandés

### Jalon 1

**Fin Lot 0**

Le repo est propre, le périmètre est figé, les données de base existent.

### Jalon 2

**Fin Lot 1**

Une exécution locale ou semi-locale produit une recommandation de campagne cohérente.

### Jalon 3

**Fin Lot 2**

Le POC est déployable sur AWS et démontrable rapidement.

### Jalon 4

**Fin Lot 3**

La démo est testable, explicable et suffisamment robuste pour une présentation externe.

---

## Définition du succès MVP

Le MVP est réussi si les conditions suivantes sont réunies :

- déploiement rapide sur AWS
- orchestration multi-agents visible
- recommandations compréhensibles
- scores et justifications traçables
- limites du système explicitement affichées
- extension possible sans refonte majeure

---

## Recommandation pragmatique

Le meilleur chemin n'est pas de commencer par "faire de l'AWS", mais de verrouiller d'abord un **flux métier déterministe + explicable**.  
Ensuite seulement, il faut l'habiller avec AgentCore pour démontrer l'orchestration, les agents, les hooks, les skills et les guardrails.

En pratique :

1. construire un moteur simple qui marche
2. le brancher à AgentCore
3. automatiser la démo
4. industrialiser plus tard
