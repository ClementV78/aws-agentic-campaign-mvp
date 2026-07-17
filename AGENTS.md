# AGENTS.md

## Mission du projet

Ce projet est un **projet vitrine portfolio**.

Son objectif n'est pas de construire une plateforme adtech complète, mais de démontrer de manière crédible et rapide :

- une capacité de **design AI / agentic systems**
- une capacité de **cloud architecture AWS**
- une capacité de **delivery pragmatique sous contrainte de temps**

La valeur principale à démontrer est la suivante :

**concevoir un MVP agentique sur AWS, simple, explicable, déployable rapidement, et techniquement défendable en entretien ou en revue d'architecture.**

---

## Positionnement

Le projet doit parler à un public de type :

- acteur de la publicité extérieure
- opérateur média contextuel
- entreprise intéressée par l'optimisation de campagnes urbaines

Règle stricte :

- **ne jamais mentionner le nom de l'entreprise cible explicitement interdite par le propriétaire du projet**
- éviter toute formulation qui donne l'impression que le projet a été produit pour une marque ou un groupe identifié

Règle complémentaire :

- les **marques annonceurs utilisées dans les jeux de données, scénarios et démonstrations doivent au contraire être réalistes, connues et variées**
- privilégier des annonceurs de catégories différentes pour enrichir les arbitrages métier

Le projet doit rester :

- générique
- élégant
- crédible
- démonstratif

---

## Profil du propriétaire du repo

Le propriétaire du projet est :

- DevOps / Cloud Architect
- en évolution vers AI Architect
- orienté architecture, orchestration, AWS, systèmes agentiques
- **non focalisé MLOps**

En conséquence, les contributions doivent valoriser en priorité :

- l'architecture
- l'orchestration
- les patterns d'agents
- l'intégration AWS
- les guardrails
- l'observabilité
- la qualité du raisonnement système

À l'inverse, il faut éviter de dériver le projet vers :

- du training ML
- du fine-tuning complexe
- des pipelines data lourds
- des sujets MLOps non nécessaires au MVP

---

## Priorité absolue

Le délai est très court.

La règle principale est donc :

**aller à l'essentiel et maximiser la valeur de démonstration.**

Chaque décision doit être évaluée selon cette question :

**"Est-ce que cela améliore clairement la démonstration des capacités IA AWS et agentiques du MVP ?"**

Si la réponse est non, le sujet doit être :

- supprimé
- simplifié
- ou repoussé en post-MVP

---

## Ce que le projet doit démontrer

Le projet doit rendre visibles les compétences suivantes :

- usage d'**AWS Bedrock / AgentCore**
- orchestration **multi-agents**
- usage de **skills**
- usage de **hooks**
- séparation entre logique déterministe et arbitrage LLM
- raisonnement contextualisé à partir d'un `CityContext`
- explicabilité des recommandations
- guardrails minimaux mais sérieux
- déploiement rapide sur AWS

La démo doit permettre de raconter clairement :

1. le problème métier simplifié
2. la construction du contexte
3. le rôle des agents
4. la logique de décision
5. les limites assumées du MVP

---

## Ce que le projet ne doit pas devenir

Ne pas transformer ce repo en :

- produit de production complet
- plateforme SaaS
- projet front-end avancé
- cartographie temps réel
- moteur d'optimisation mathématique sophistiqué
- démonstrateur MLOps
- gros projet Terraform / CI/CD avant stabilisation du MVP

Si un choix oppose :

- `effet vitrine rapide et crédible`
- `complétude technique lourde`

il faut privilégier le premier.

---

## Principes produit

Le MVP repose sur des hypothèses assumées :

- inventaire simplifié
- zones fictives ou simplifiées
- annonceurs réalistes, connus et suffisamment différents pour produire des recommandations crédibles
- recommandations indicatives
- absence de disponibilité réelle des panneaux

Règles :

- ne jamais faire croire que le système exploite un inventaire réel
- ne jamais présenter les résultats comme une allocation opérationnelle réelle
- toujours expliciter les hypothèses et limites

---

## Principes d'architecture

### 1. Démontrer d'abord un flux bout en bout

Avant toute sophistication :

- entrée
- pré-hook
- `CityContext`
- skills
- allocation
- review
- sortie

Un flux simple qui fonctionne vaut mieux qu'une architecture ambitieuse incomplète.

### 2. Deterministic first

Le scoring principal doit être **déterministe, lisible et testable**.

Les LLM doivent être utilisés prioritairement pour :

- extraction
- classification légère
- arbitrage limité
- synthèse
- explication
- revue de cohérence

Éviter :

- scoring opaque confié entièrement au LLM
- décisions impossibles à justifier

### 3. AWS first, but only where it adds demo value

Utiliser AWS quand cela renforce la démonstration.

Ne pas ajouter de composants AWS juste pour "faire cloud".

Chaque composant doit avoir une justification simple :

- AgentCore pour l'orchestration agentique
- Bedrock pour les modèles
- Gateway pour exposer le flux
- scripts CLI pour déployer vite

### 4. Minimal infrastructure

Pour le MVP :

- privilégier `Bash + AWS CLI + AgentCore CLI`
- limiter Terraform / OpenTofu au post-MVP sauf besoin évident
- viser un déploiement rapide et réversible

### 5. Observability by default

Même sur un POC, il faut conserver :

- logs d'orchestration
- entrées/sorties des étapes critiques
- traces des décisions de scoring
- raisons de confiance ou de faible confiance

---

## Règles d'implémentation

### Structure

Respecter autant que possible la structure cible :

- `data/`
- `agents/`
- `skills/`
- `hooks/`
- `tools/`
- `tests/`
- `scripts/`
- `docs/`

### Data model

Le périmètre MVP courant est :

- `20 zones`
- `5 annonceurs`

Ne pas ré-élargir ce scope sans validation explicite.

Pour les annonceurs :

- choisir des marques réelles et reconnaissables
- maximiser la diversité des secteurs, audiences et contextes d'activation
- éviter les portfolios trop homogènes

### Complexity budget

Toute contribution doit limiter :

- la profondeur d'orchestration
- le nombre de dépendances
- le nombre de services AWS annexes
- le volume de configuration manuelle

### Scripts

Les scripts de déploiement doivent être :

- lisibles
- relançables autant que possible
- explicites sur les prérequis
- explicites sur les ressources créées
- prudents sur les coûts

Prévoir si possible :

- `bootstrap.sh`
- `deploy.sh`
- `demo.sh`
- `destroy.sh`

### Security

Même pour un MVP :

- éviter les permissions IAM `*` si une alternative raisonnable existe
- documenter les permissions larges si elles sont provisoirement nécessaires
- ne jamais commiter de secrets
- éviter les données réelles sensibles

### Cost control

Toujours garder en tête :

- coût Bedrock
- coût des invocations répétées
- coût des ressources oubliées

Le nettoyage de l'environnement est une fonctionnalité importante du projet.

---

## Règles sur les agents

Les agents doivent rester peu nombreux et utiles.

Critères :

- chaque agent a une responsabilité claire
- chaque skill a une valeur démontrable
- la frontière entre agents n'est pas artificielle

Éviter :

- découpage excessif en micro-agents
- architecture complexe juste pour impressionner
- enchaînements LLM inutiles

Le projet doit montrer de la **maîtrise**, pas de la complexité décorative.

---

## Règles sur les sorties

Chaque résultat important doit idéalement contenir :

- un score
- une justification
- un niveau de confiance
- les hypothèses ou limites principales

Le système doit être capable d'expliquer :

- pourquoi une zone est recommandée
- pourquoi un annonceur est favorisé
- quels signaux ont influencé la décision

---

## Règles de communication et documentation

Les assistants travaillant sur ce repo doivent :

- être concis
- être pragmatiques
- expliciter les hypothèses
- distinguer clairement faits, hypothèses et incertitudes
- signaler les raccourcis pris pour tenir le délai

Pour les changements non triviaux :

1. expliquer brièvement ce qui va être modifié
2. indiquer pourquoi c'est pertinent pour le MVP
3. éviter les grosses modifications silencieuses

Le code, les identifiants techniques, les variables et les commentaires doivent être en **anglais**.  
La documentation peut être en **français** ou en **anglais** selon le contexte, mais doit rester cohérente dans un même document.

---

## Critères de décision

En cas d'hésitation, choisir l'option qui maximise :

- la clarté de la démo
- la crédibilité architecturale
- la vitesse d'exécution
- l'explicabilité
- la réversibilité

et qui minimise :

- la complexité cachée
- le temps d'implémentation
- le coût AWS
- la dette d'infrastructure prématurée

---

## Définition du succès

Le projet est réussi si un lecteur ou un recruteur comprend rapidement que le propriétaire sait :

- cadrer un problème métier
- simplifier intelligemment un domaine complexe
- concevoir une architecture agentique AWS cohérente
- séparer logique métier et usage LLM
- livrer un POC démontrable sous forte contrainte de temps

---

## Anti-patterns à éviter absolument

- mentionner l'entreprise cible interdite comme sponsor, cible ou client implicite
- gonfler artificiellement le nombre d'agents
- laisser le LLM piloter toute la décision sans logique vérifiable
- ajouter Terraform, CI/CD ou UI lourde trop tôt
- confondre MVP de démonstration et produit de production
- cacher les limites du système
- sacrifier la lisibilité pour une apparence "impressionnante"
