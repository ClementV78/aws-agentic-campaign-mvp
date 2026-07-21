# Archive — Analyse infra Lot 2 (instruction de décision)

> **Document archivé.** Il a servi à instruire le choix d'architecture infra du Lot 2.
> Les décisions retenues sont désormais portées par [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
> (§5 architecture cible, §10 NFR, §13 décisions, §14 risques).
> Les procédures opérationnelles ont été extraites vers [../RUNBOOK_DEPLOY.md](../RUNBOOK_DEPLOY.md).
>
> Conservé pour la traçabilité du raisonnement, pas comme source de vérité.

---

# Lot 2 Infra MVP

## Objectif

Définir une cible infra AWS **minimale, démontrable et réversible** pour sortir du mode purement local sans transformer le projet en plateforme complexe.

Cette note sert à cadrer le Lot 2 avant de modifier `deploy.sh` et `destroy.sh`.

---

## Résumé exécutif

Recommandation pour le MVP infra :

- `Bedrock AgentCore Runtime` comme coeur exécutable du MVP
- un **Strands agent métier** comme point d'orchestration dans ce runtime
- un **noyau déterministe** conservé pour `CityContext`, scoring, allocation et review structurée
- `InvokeAgentRuntime` comme premier chemin d'invocation à fermer
- `AgentCore Gateway` comme surface cible des tools de contexte pour auth, policy, guardrails et observabilité
- `API Gateway + AWS_IAM / SigV4` seulement si la démo a besoin d'un endpoint HTTP classique
- `Amazon Bedrock` pour les appels LLM optionnels
- `S3` pour les données projet, les sorties de harness et les artefacts simples
- `CloudWatch Logs` pour l'observabilité de base
- `IAM` minimal, centré sur `bedrock:InvokeModel`, `logs:*` sur le groupe dédié, et accès ciblé au bucket S3 du projet
- bucket S3 durci par défaut : chiffrement, blocage public, ownership controls, versioning
- `deploy.sh` produit aussi un `deploy-outputs.json` pour réutiliser les sorties de déploiement côté teardown, smoke et harness

Choix assumé :

- faire d'`AgentCore` et de `Bedrock` le coeur de la cible POC
- conserver la séparation `tools / agents / hooks / deterministic core` pour garder une architecture défendable

Raison principale :

- c'est le chemin le plus cohérent pour raconter une **démo AWS agentique réelle**, multi-agent et multi-LLM, sans laisser le local devenir le message principal du projet

---

## Contexte de charge

### Faits

- projet portfolio, pas produit de production
- délai court
- moteur local fonctionnel déjà implémenté
- scoring principal déterministe
- usage LLM optionnel pour `Events Agent`, `Review Agent`, `Executive Summary`
- scripts infra encore placeholders

### Hypothèses

- un seul compte AWS de démo
- une seule région AWS
- faible trafic, exécution manuelle ou semi-manuelle
- aucune donnée sensible métier réelle
- pas d'exigence multi-AZ métier forte pour le MVP

### Inconnues

- région AWS cible
- modèle Bedrock exact visé en production démo
- besoin réel ou non d'un endpoint public persistant pour la démo

---

## Pondération des piliers

### Poids

- `Operational Excellence`: 5
- `Cost Optimization`: 5
- `Security`: 4
- `Reliability`: 3
- `Performance Efficiency`: 2
- `Sustainability`: 2

### Justification

- `Operational Excellence` est dominant car l'objectif du lot est un déploiement rapide, lisible et réversible
- `Cost Optimization` est dominant car le MVP doit éviter toute infra décorative ou permanente coûteuse
- `Security` reste importante même sur un POC, surtout sur IAM et exposition publique
- `Reliability` doit être correcte mais proportionnée à une démo portfolio
- `Performance Efficiency` n'est pas critique vu le faible trafic attendu
- `Sustainability` est secondaire à ce stade, sans être ignorée

Implication pratique :

- pas de VPC tant qu'il n'y a pas de ressource privée à joindre
- pas d'EKS
- pas de base de données managée
- pas de multi-région
- peu de composants, tous managés

---

## Architecture recommandée

```text
Client AWS or harness
  -> InvokeAgentRuntime
  -> Bedrock AgentCore runtime
      -> Strands business agent
      -> AgentCore Gateway tools
      -> deterministic decision core
      -> Bedrock model access
  -> S3 project data and harness outputs
  -> CloudWatch Logs

Optional HTTP exposure later:
HTTP client
  -> API Gateway HTTP API
  -> AWS_IAM / SigV4
  -> AgentCore Runtime
```

### Composants

#### 1. Bedrock AgentCore Runtime

Rôle :

- héberger le vrai flux métier agentique
- porter le **Strands agent métier** retenu comme cible
- fournir la première cible AWS réellement exécutable du MVP

Pourquoi ce choix :

- c'est la capacité AgentCore centrale à démontrer
- la doc AWS pousse d'abord un runtime `HTTP` cohérent avant d'ajouter d'autres briques
- cela permet de raconter une cible plus portfolio-friendly sans sacrifier le noyau déterministe

#### 1.b Strands agent métier

Rôle :

- orchestrer le flux métier dans le runtime AgentCore
- choisir le chemin `scenario` ou `live`
- appeler les tools nécessaires
- déléguer le calcul critique au noyau déterministe du projet

Pourquoi ce choix :

- c'est la cible architecture désormais retenue
- cela matérialise mieux la dimension agentique du MVP
- cela reste défendable si le scoring et l'allocation ne sont pas déplacés dans le prompt principal

#### 2. Invocation directe via `InvokeAgentRuntime`

Rôle :

- fermer le premier chemin d'invocation end-to-end
- éviter d'ajouter trop tôt une façade HTTP supplémentaire

Pourquoi ce choix :

- c'est le chemin natif AgentCore
- c'est le plus court pour valider le runtime réel

#### 3. AgentCore Gateway

Rôle :

- exposer les tools de contexte et de données à l'orchestrateur agentique
- préserver des contrats stables entre collecte brute et interprétation métier
- porter la couche de gouvernance de sécurité générique

Pourquoi ce choix :

- l'agent doit appeler de vrais tools observables et gouvernés
- Gateway est l'endroit naturel pour porter auth, policies, guardrails et traces de tool calls
- cela évite de réimplémenter en hooks custom des contrôles génériques déjà couverts par AWS

#### 4. API Gateway HTTP API

Rôle :

- exposer plus tard un endpoint HTTP classique si la démo en a besoin
- fournir une façade plus familière pour un client externe, un frontend ou un webhook

Pourquoi ce choix :

- optionnel pour AgentCore Runtime
- utile seulement si l'invocation via SDK/API AgentCore n'est pas suffisante pour la démo

#### 5. S3

Rôle :

- stocker les données MVP versionnées si on veut les externaliser du package
- stocker éventuellement les outputs de démo
- garder un point simple pour les artefacts

Pourquoi ce choix :

- simple, durable, natif AWS
- utile sans imposer une base de données

#### 6. Amazon Bedrock

Rôle :

- fournir les appels LLM quand `EVENTS_AGENT_MODE`, `REVIEW_AGENT_MODE` ou `EXECUTIVE_SUMMARY_MODE` sont activés

Pourquoi ce choix :

- aligne la démo avec la cible AWS
- remplace avantageusement OpenRouter dans la version AWS

#### 7. CloudWatch Logs

Rôle :

- centraliser les logs d'exécution
- tracer les décisions critiques, le scénario, les providers utilisés et les warnings

Pourquoi ce choix :

- indispensable pour une démo défendable
- coût faible si la rétention est bornée

---

## Ce qu'on ne met pas dans le MVP infra

- `EKS`
- `ECS`
- `RDS`
- `VPC` dédiée sans besoin privé avéré
- `Terraform/OpenTofu` avant stabilisation
- `Step Functions`
- `EventBridge` pour l'orchestration principale
- `AWS Lambda` comme architecture canonique du POC

Raison :

- ces briques augmentent la complexité, le temps de setup, et le coût cognitif sans améliorer clairement la démonstration MVP à ce stade

---

## Position sur AgentCore

### Recommandation

Traiter `AgentCore` comme le **runtime cible du POC**, pas comme une évolution cosmétique.

### Pourquoi

- le but du projet est de montrer une solution agentique AWS crédible
- le premier message à rendre vrai est : le runtime AWS exécute réellement le flux métier
- `Gateway` fait partie de la cible car il porte la gouvernance des tools

### Ce qu'il faut préparer dès maintenant

- garder les interfaces tools stables
- expliciter la frontière entre raisonnement déterministe et usage LLM
- faire porter les blocages génériques par Guardrails / Policy / Gateway
- réserver les hooks custom aux règles métier et à la readiness des données
- prévoir un premier chemin `InvokeAgentRuntime`
- n'ajouter `AWS_IAM` via `API Gateway` qu'en cas de besoin d'exposition HTTP
- prévoir le harness sur la même cible finale

---

## Découpage recommandé du Lot 2

### 2A. AWS deployable target

Livrer :

- un runtime `Bedrock AgentCore`
- une invocation directe `InvokeAgentRuntime` qui fonctionne
- un bucket S3 projet
- un rôle IAM minimal
- des variables d'environnement centralisées
- des logs CloudWatch propres
- un `AgentCore Gateway`
- éventuellement un endpoint `API Gateway + AWS_IAM`
- un harness de scénarios branché sur la même cible finale
- `deploy.sh` et `destroy.sh` réellement utiles

Critère de sortie :

- un scénario et un run de harness peuvent être lancés sur AWS via le runtime réel

---


## Principaux risques

### [Medium] Smoke test signé encore manuel
Piliers: Operational Excellence, Security
Evidence: `deploy.sh` sait préparer le contexte mais n'invoque pas encore automatiquement la cible finale, que ce soit via `InvokeAgentRuntime` ou via un éventuel endpoint `AWS_IAM`.
Impact: une partie de la validation reste manuelle après déploiement.
Recommendation: figer d'abord un smoke test stable sur la cible principale, puis seulement ajouter un chemin signé si une façade HTTP est retenue.
Trade-off: un peu plus d'effort de scripting, mais une démo plus propre.
Confidence: High

### [Medium] Surconstruire l'infra pour un workload de démo
Piliers: Cost Optimization, Operational Excellence
Evidence: le trafic prévu est faible et le système est essentiellement déclenché à la demande.
Impact: temps perdu, maintenance inutile, coût plus élevé.
Recommendation: rester sur du serverless managé et peu de composants.
Trade-off: moins de sophistication, mais meilleure vitesse d'exécution.
Confidence: High

### [Medium] IAM trop permissif pour gagner du temps
Piliers: Security
Evidence: les scripts de déploiement n'existent pas encore et la tentation du `*` est forte en MVP.
Impact: posture sécurité faible et architecture moins défendable en entretien.
Recommendation: cadrer tout de suite les permissions minimales par rôle.
Trade-off: un peu plus de travail initial sur les scripts.
Confidence: High

---

## Décisions recommandées maintenant

1. Garder `InvokeAgentRuntime + AgentCore Runtime + Bedrock + S3 + CloudWatch` comme noyau POC.
2. Ajouter `AgentCore Gateway` comme surface cible des tools et de leur gouvernance.
3. Attacher `Policy` et `Bedrock Guardrails` sur cette surface plutôt que réimplémenter les blocages génériques.
4. N'ajouter `API Gateway + AWS_IAM` que si la démo a besoin d'un endpoint HTTP classique.
5. Continuer à restreindre l'IAM autour des seuls besoins runtime et déploiement.

---

## Ce qui ferait changer cette recommandation

- besoin d'orchestration longue, asynchrone ou multi-étapes avec état
- besoin de ressources privées nécessitant VPC et connectivité dédiée
- forte exigence de reproductibilité infra par IaC dès maintenant
