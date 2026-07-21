
# Urban Campaign Intelligence
## PRD / Cahier des charges technique (MVP)

Version: 0.1
Objectif: construire en 1 à 2 jours un POC démontrant une architecture multi-agents AWS Bedrock AgentCore, orientée orchestration, avec un minimum d'infrastructure.

---

# Vision

Le système optimise l'allocation de campagnes DOOH sur 20 zones parisiennes en fonction du contexte urbain.

Il ne connaît pas un inventaire réel de panneaux. Il raisonne sur un inventaire simplifié de zones afin de démontrer les capacités d'AgentCore.

---

# Objectifs

- AWS Bedrock AgentCore
- AgentCore Gateway
- Multi-agents
- Skills
- Multi-LLM
- Hooks
- Guardrails
- Harness de test
- Déploiement rapide

Hors périmètre:
- CI/CD
- Authentification
- Terraform complet
- Cartographie (Lot 2)
- UI avancée

---

# Cas d'usage

Entrée :

- ville (défaut Paris)
- date/heure (optionnelle, sinon maintenant)
- simulation éventuelle

Pré-hook :
- normalisation date/heure
- calcul du time slot
- création du TimeContext

Construction du CityContext :

- météo
- événements
- mobilité
- calendrier
- vacances
- contexte urbain

Les agents métier consomment ensuite uniquement le CityContext.

---

# Architecture logique

User

→ Pre-hook

→ Supervisor Agent

    - Weather Agent
    - Events Agent
    - Mobility Agent
    - Zones Repository
    - Advertisers Repository

→ City Context Builder

→ Zone Analyzer Agent

→ Advertiser Matcher Agent

→ Campaign Allocation Agent

→ Review Agent / Guardrails

→ Post-hook

---

# Données

## Zones (20)

Catégories :

- Gares
  - Gare du Nord
  - Gare de Lyon
  - Gare Montparnasse
  - Gare Saint-Lazare

- Tourisme
  - Tour Eiffel
  - Louvre
  - Champs-Élysées
  - Montmartre

- Quartiers d'affaires
  - La Défense
  - Opéra

- Evénementiel
  - Accor Arena
  - Parc des Princes
  - Stade de France

- Commercial
  - Boulevard Haussmann
  - Forum des Halles

- Premium
  - Avenue Montaigne
  - Saint-Germain-des-Prés

- Famille / Loisirs
  - Vincennes

- Hubs
  - Châtelet
  - République

Chaque zone contient :

- type
- audience
- traffic_level
- premium_index
- weather_sensitivity
- audience_by_time

## Annonceurs

5 annonceurs :

- Coca-Cola
- Chanel
- OUIGO
- Nike
- Parc Asterix

Chaque annonceur :

- audience cible
- contextes favoris
- exclusions
- priorité

---

# Algorithme

Score(zone, annonceur)

- audience match
- météo
- événements
- mobilité
- compatibilité horaire
- attractivité
- exclusions
- pénalité risque

Puis allocation.

---

# Sorties

## Dashboard

- contexte
- météo
- événements
- confiance

## Planning par annonceur

Annonceur

→ zones

→ score

→ justification

## Planning par zone

Zone

→ annonceur

→ score

→ justification

## Rapport d'explication

- critères
- score
- confiance

## Journal d'orchestration

Chronologie des agents.

---

# Multi-LLM

Petit modèle

- extraction
- classification
- interprétation contexte météo / événements / mobilité

Grand modèle

- arbitrage
- synthèse
- rapport final

---

# Guardrails

## System Prompt

- pas d'inventaire réel
- pas de disponibilité réelle
- allocation indicative
- explication obligatoire
- confidence obligatoire
- brand safety

## Skills

Allocation

- appliquer scoring
- exclusions
- saturation
- double planning

Review

- hallucinations
- cohérence
- diversité
- justification

## Hooks

Pre-hook

- validation
- normalisation
- TimeContext

Tool hook

- validation JSON
- logs
- contrôle données

Post-hook

- contrôle hallucinations
- confiance
- avertissements

---

# Harness

Scénarios :

- canicule
- pluie
- concert
- grève
- fashion week
- week-end

Validation automatique :

- cohérence
- justification
- confiance
- diversité

---

# Déploiement rapide

Objectif : moins d'une journée.

## Phase 1

- AWS CLI
- Bedrock
- AgentCore
- Gateway

Commandes CLI uniquement.

## Phase 2

Déploiement automatique.

Deux options :

### Option A (recommandée pour le MVP)

Scripts Bash + AWS CLI.

Avantages :

- extrêmement rapide
- lisible
- aucun état Terraform
- parfait pour un POC

Scripts :

scripts/bootstrap.sh

scripts/deploy.sh

scripts/destroy.sh

scripts/demo.sh

### Option B

Terraform léger.

Ne gérer que :

- IAM
- Lambda
- Gateway
- éventuellement S3

Laisser le reste au CLI.

### Option C (Lot 2)

Infrastructure entièrement en Terraform/OpenTofu avec GitHub Actions.

---

# Structure du dépôt

```
urban-campaign-intelligence/
│
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── data/
├── agents/
├── skills/
├── hooks/
├── tools/
├── tests/
├── scripts/
│   ├── bootstrap.sh
│   ├── deploy.sh
│   ├── destroy.sh
│   └── demo.sh
└── docs/
```

---

# Recommandation

Pour ce MVP, privilégier les scripts Bash + AWS CLI + AgentCore CLI plutôt que Terraform.

L'objectif est de démontrer rapidement l'architecture agentique. Terraform pourra être introduit dans un second temps lorsque l'infrastructure sera stabilisée.

Le succès du POC sera mesuré sur :
- simplicité de déploiement (<15 minutes sur un compte AWS vide)
- orchestration multi-agents
- qualité des recommandations
- explicabilité
- facilité d'extension.


````md
# One-Click Deploy

## Objectif

Permettre de déployer et de démontrer le POC sur un compte AWS dédié en quelques commandes, avec un minimum de prérequis et sans configuration manuelle complexe.

Le but n'est **pas** de proposer une chaîne de déploiement de niveau production, mais d'obtenir un environnement fonctionnel le plus rapidement possible afin de se concentrer sur les fonctionnalités AgentCore.

---

# Philosophie

Le MVP privilégie :

- la simplicité
- la rapidité de mise en œuvre
- la reproductibilité
- une démonstration rapide

Les scripts supposent un compte AWS propre (ou un environnement de démonstration dédié).

L'objectif est de pouvoir passer du clonage du dépôt à une démonstration fonctionnelle en moins de 15 minutes.

---

# Workflow

```text
git clone <repository>

cd urban-campaign-intelligence

./bootstrap.sh

./deploy.sh

./demo.sh
```

Une fois la démonstration terminée :

```text
./destroy.sh
```

---

# bootstrap.sh

Prépare l'environnement de développement.

Exemples :

- vérification des prérequis
  - AWS CLI
  - AgentCore CLI
  - Python
  - NodeJS
- vérification des credentials AWS
- vérification de la région AWS
- installation des dépendances Python
- installation des dépendances NodeJS

Le script ne crée aucune ressource AWS.

---

# deploy.sh

Déploie le POC.

Exemples :

- création des rôles IAM nécessaires
- déploiement des Lambda Tools
- création de l'AgentCore Gateway
- déploiement des Agents
- déploiement des Skills
- configuration des Hooks
- chargement des données de démonstration
- configuration des modèles Bedrock

À la fin du script, le workflow est immédiatement exécutable.

---

# demo.sh

Lance automatiquement plusieurs scénarios métier.

Exemples :

- Canicule
- Concert à Bercy
- Fashion Week
- Grève SNCF
- Week-end touristique

Pour chaque scénario :

- affichage du contexte détecté
- exécution du workflow multi-agents
- affichage des recommandations
- journal d'orchestration
- temps d'exécution
- coût estimatif (optionnel)

Le but est de disposer d'une démonstration reproductible en quelques minutes.

---

# destroy.sh

Supprime toutes les ressources créées par le POC.

Objectifs :

- éviter les coûts AWS
- repartir d'un environnement propre
- faciliter les démonstrations successives

---

# Principes d'implémentation

Pour le MVP, privilégier :

- Bash
- AWS CLI
- AgentCore CLI

L'objectif est de réduire le temps de développement au maximum.

Terraform / OpenTofu pourront être introduits dans un second temps lorsque l'architecture sera stabilisée.

---

# Hors périmètre du MVP

Le One-Click Deploy ne cherche pas à fournir :

- une infrastructure de niveau production
- une idempotence complète
- un pipeline CI/CD
- une gestion avancée des mises à jour
- un déploiement multi-environnements

Ces aspects seront traités dans une phase d'industrialisation ultérieure.

---

# Critères de succès

- Déploiement complet en moins de 15 minutes sur un compte AWS dédié.
- Aucune configuration manuelle complexe.
- Workflow immédiatement exécutable après le déploiement.
- Démonstration automatisée via `demo.sh`.
- Nettoyage complet de l'environnement via `destroy.sh`.
````
