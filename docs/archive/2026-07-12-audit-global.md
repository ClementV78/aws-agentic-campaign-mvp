# Audit global du projet

Date: 2026-07-12

Portée:

- architecture cible et architecture locale
- cohérence documentaire
- delivery, scripts et préparation au déploiement AWS

Audience:

- propriétaire du repo
- reviewer technique
- recruteur / interviewer Cloud Architect / AI Architect

Méthode:

- `idp-documentation-engineer` pour la cohérence documentaire et la qualité de la preuve
- `aws-architecture-review` pour la lecture AWS / Well-Architected
- `idp-devops-engineer` pour la lecture delivery, scripts, validation, rollback et opérabilité

Statut de validation:

- faits vérifiés sur fichiers du repo et commandes locales
- aucune validation cloud live effectuée dans cet audit
- `deploy.sh` et `destroy.sh` validés en syntaxe et en `dry-run`

---

## 1. Résumé exécutif

Le projet est déjà crédible sur son **Lot 1**: moteur local complet, séparation déterministe / LLM propre, contrats tools stabilisés, scénarios de démo cohérents, et base documentaire nettement au-dessus du niveau habituel d'un POC portfolio.

Le principal écart n'est plus "absence d'infra", mais **incomplétude du Lot 2**. La cible `API Gateway + AWS_IAM + AgentCore + AgentCore Gateway + Bedrock + S3 + CloudWatch` est bien documentée, mais la démonstration AWS de bout en bout n'est pas encore fermée.

Conclusion courte:

- `Lot 1`: terminé et défendable
- `Lot 2`: bien cadré, partiellement implémenté, pas encore démontrable de bout en bout
- valeur portfolio: déjà forte sur la pensée système, encore incomplète sur la preuve d'exécution AWS agentique

---

## 2. Cadre de revue

### Faits

- moteur local Python implémenté sous [src/urban_campaign_intelligence](/home/xclem/projetsperso/agentic-campaign/src/urban_campaign_intelligence)
- 16 tests locaux passent
- cible AWS centrée sur `AgentCore` documentée dans [ARCHITECTURE.md](/home/xclem/projetsperso/agentic-campaign/ARCHITECTURE.md) et [docs/LOT2_INFRA_MVP.md](2026-07-lot2-infra-analyse.md)
- `deploy.sh` et `destroy.sh` existent et sont utilisables en `dry-run`
- le projet AgentCore cible est centralisé sous [agentcore-project/UrbanCampaignIntelligencePoc](/home/xclem/projetsperso/agentic-campaign/agentcore-project/UrbanCampaignIntelligencePoc)

### Hypothèses

- le but prioritaire reste une démonstration portfolio, pas une plateforme de production
- un seul compte AWS et une seule région suffisent pour la démo
- l'authentification cible doit rester minimale mais sérieuse, via `AWS_IAM` et non `Basic Auth`

### Inconnues

- mapping Bedrock final par agent
- forme exacte de l'endpoint final et du payload signé
- contenu futur de `aws-targets.json` pour un déploiement live AgentCore

---

## 3. Forces constatées

### Architecture et design

- La séparation entre **raisonnement déterministe** et **usage LLM** est nette et cohérente avec l'objectif du portfolio.
- `CityContext` joue bien son rôle d'objet pivot entre collecte et décision.
- Les contrats tools sont pensés pour survivre au remplacement des providers locaux par `AgentCore Gateway`.

### Documentation

- Le repo explicite bien le scope, les limites et les hypothèses.
- La cible AWS est racontable en entretien.
- Les documents de suivi et de cadrage ont des rôles distincts et globalement bien tenus.

### Delivery / scripts

- `deploy.sh` durcit déjà le bucket S3, produit un manifest, et génère `deploy-outputs.json`.
- `destroy.sh` exploite ces sorties pour piloter le teardown.
- la logique reste lisible, pragmatique, et adaptée à un POC.

---

## 4. Findings priorisés

### F1 - `High` - La démo AWS n'est pas encore fermée de bout en bout

Faits:

- la cible AWS est documentée comme `AgentCore-first`
- `AgentCore Gateway` est encore `todo` dans [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md:144)
- le smoke test signé sur endpoint `AWS_IAM` reste manuel ou non branché

Impact:

- le message portfolio "je sais déployer une solution agentique AWS multi-agent / multi-LLM" n'est pas encore entièrement prouvé par exécution

Preuves:

- [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md:141)
- [docs/LOT2_INFRA_MVP.md](2026-07-lot2-infra-analyse.md:334)
- [scripts/deploy.sh](/home/xclem/projetsperso/agentic-campaign/scripts/deploy.sh:19)

Recommandation:

- brancher d'abord `AgentCore Gateway`
- figer ensuite un smoke test `SigV4` appelant le même endpoint que le futur harness

### F2 - `High` - Le projet AgentCore cible n'est pas encore déployable en live

Faits:

- `deploy.sh` désactive volontairement le déploiement live quand aucun target n'est configuré
- `aws-targets.json` n'est pas encore peuplé

Impact:

- la chaîne de déploiement existe, mais la preuve cloud réelle reste bloquée

Preuves:

- [scripts/deploy.sh](/home/xclem/projetsperso/agentic-campaign/scripts/deploy.sh:289)
- [agentcore.json](/home/xclem/projetsperso/agentic-campaign/agentcore-project/UrbanCampaignIntelligencePoc/agentcore/agentcore.json:1)
- [outputs/deploy/deploy-outputs.json](/home/xclem/projetsperso/agentic-campaign/outputs/deploy/deploy-outputs.json:1)

Recommandation:

- remplir `agentcore/aws-targets.json`
- valider un premier `agentcore deploy` sur un environnement de démo jetable

### F3 - `Resolved` - `bootstrap.sh` reflète maintenant les prérequis du Lot 2

Faits:

- `bootstrap.sh` vérifie maintenant `python3`, `aws`, `zip`, `node`, `npm`, `npx`, `agentcore`
- le script contrôle aussi la région AWS, l'identité AWS, la structure du projet AgentCore cible et l'état de `aws-targets.json`
- `agentcore validate` est exécuté
- les tests locaux peuvent être lancés ou désactivés via `RUN_LOCAL_TESTS`

Impact:

- le script est désormais exploitable comme vrai bootstrap de Lot 2

Preuves:

- [scripts/bootstrap.sh](/home/xclem/projetsperso/agentic-campaign/scripts/bootstrap.sh:1)
- [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md:139)

Recommandation:

- maintenir ce niveau de vérification en phase avec l'évolution du Lot 2

### F4 - `Resolved` - Le README a été réaligné avec l'état réel

Faits:

- le README décrit désormais l'état réel du Lot 2
- `outputs/` apparaît dans la structure du repo
- une section `Known limitations` explicite les manques restants
- les scripts infra et leurs usages `dry-run` sont documentés

Impact:

- le risque de sous-estimer l'avancement du Lot 2 est réduit

Preuves:

- [README.md](/home/xclem/projetsperso/agentic-campaign/README.md:17)
- [README.md](/home/xclem/projetsperso/agentic-campaign/README.md:36)

Recommandation:

- maintenir cet alignement à chaque étape du Lot 2

### F5 - `Resolved` - Les schémas historiques sont désormais explicitement marqués comme non canoniques

Faits:

- les schémas historiques sont maintenant distingués des schémas canoniques
- la règle d'usage est documentée directement dans `docs/diagrams/README.md`

Impact:

- le risque de confusion est réduit tant que les documents futurs pointent vers les schémas canoniques

Preuves:

- [docs/diagrams/README.md](/home/xclem/projetsperso/agentic-campaign/docs/diagrams/README.md:1)
- [ARCHITECTURE.md](/home/xclem/projetsperso/agentic-campaign/ARCHITECTURE.md:35)

Recommandation:

- continuer à référencer uniquement les schémas canoniques dans la doc principale

### F6 - `Medium` - L'observabilité et l'évaluation existent localement, pas encore côté AWS

Faits:

- les tests locaux sont bons
- aucun harness AWS complet n'est encore branché
- les traces CloudWatch sont prévues mais non démontrées

Impact:

- la réexécution et la preuve de qualité restent principalement locales

Preuves:

- [tests/test_runner.py](/home/xclem/projetsperso/agentic-campaign/tests/test_runner.py:1)
- [docs/STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md:127)
- [docs/LOT2_INFRA_MVP.md](2026-07-lot2-infra-analyse.md:310)

Recommandation:

- créer un premier harness AWS léger réutilisant `scenario_id`
- capturer réponse, durée, warning count et top recommendation

### F7 - `Low` - Le repo n'est pas initialisé en git

Faits:

- l'environnement actuel n'est pas un dépôt git initialisé

Impact:

- moins gênant pour le code lui-même que pour la traçabilité des itérations portfolio

Recommandation:

- initialiser le dépôt avant de multiplier les itérations infra et doc

---

## 5. Lecture AWS Well-Architected adaptée au POC

### Pondération retenue

- `Operational Excellence`: très forte
- `Cost Optimization`: forte
- `Security`: forte mais proportionnée
- `Reliability`: moyenne
- `Performance Efficiency`: faible à moyenne
- `Sustainability`: secondaire

### Lecture synthétique par pilier

#### Operational Excellence

Bon niveau pour un POC:

- architecture explicitée
- backlog lisible
- scripts relançables
- séparation entre état réel et cible

Point faible:

- absence de preuve AWS de bout en bout

#### Security

Bon niveau de direction:

- rejet de `Basic Auth`
- cible `AWS_IAM`
- bucket S3 durci

Point faible:

- l'auth réelle du endpoint n'est pas encore démontrée

#### Reliability

Bon niveau local:

- fallback heuristique
- tests métier utiles

Point faible:

- aucune preuve de comportement sous runtime AWS réel

#### Performance Efficiency

Acceptable pour un portfolio:

- peu de composants
- raisonnement principalement déterministe

Risque accepté:

- pas d'optimisation particulière tant que le flux cible n'est pas branché

#### Cost Optimization

Très cohérent avec l'objectif:

- faible nombre de services
- pas de VPC tant que non nécessaire
- scripts de cleanup présents

Point de vigilance:

- ne pas laisser dériver vers une infra décorative

#### Sustainability

Sujet secondaire et correctement traité comme tel pour ce contexte

---

## 6. Lecture delivery / DevOps

### Ce qui est bon

- scripts shell simples et compréhensibles
- `destroy.sh` présent tôt, ce qui est sain pour un POC AWS
- `deploy-outputs.json` améliore la traçabilité et la réversibilité

### Ce qui manque encore

- bootstrap AWS réel
- smoke test signé automatisé
- preuve d'une séquence de déploiement reproductible en live
- documentation d'exploitation du chemin `deploy -> smoke -> destroy`

### Position recommandée pour un POC portfolio

À retenir maintenant:

- simplicité shell
- endpoint sécurisé minimal
- teardown fiable
- preuve d'orchestration agentique AWS

À ignorer pour le moment:

- CI/CD lourde
- Terraform complet
- scans supply chain avancés
- industrialisation GitOps

---

## 7. Plan d'action recommandé

### P0

1. Configurer `aws-targets.json`
2. Câbler `AgentCore Gateway`
3. Ajouter un smoke test `SigV4` rejouable

### P1

1. Mettre à jour `bootstrap.sh` pour le Lot 2
2. Aligner `README.md` avec l'état réel
3. Nettoyer les schémas historiques

### P2

1. Ajouter un harness AWS léger
2. Ajouter une note d'exploitation `deploy / smoke / destroy`
3. Étendre la preuve d'observabilité CloudWatch

---

## 8. Matrice de preuves

| Capacité / sujet | Artifact | Validation | Statut |
|---|---|---|---|
| Moteur local bout en bout | [src/urban_campaign_intelligence](/home/xclem/projetsperso/agentic-campaign/src/urban_campaign_intelligence) | lecture code + tests | `verified` |
| Tests locaux | [tests/test_runner.py](/home/xclem/projetsperso/agentic-campaign/tests/test_runner.py:1) | `PYTHONPATH=src python -m unittest discover -s tests -v` | `verified` |
| Contrats tools | [docs/GATEWAY_TOOLS.md](/home/xclem/projetsperso/agentic-campaign/docs/GATEWAY_TOOLS.md:1) | lecture doc + contrat JSON | `verified` |
| Cible AWS | [ARCHITECTURE.md](/home/xclem/projetsperso/agentic-campaign/ARCHITECTURE.md:1) | lecture doc + schémas | `verified` |
| Déploiement shell | [scripts/deploy.sh](/home/xclem/projetsperso/agentic-campaign/scripts/deploy.sh:1) | `bash -n` + `DRY_RUN=1` | `verified_partial` |
| Teardown shell | [scripts/destroy.sh](/home/xclem/projetsperso/agentic-campaign/scripts/destroy.sh:1) | `bash -n` + `DRY_RUN=1` | `verified_partial` |
| Projet AgentCore cible | [agentcore-project/UrbanCampaignIntelligencePoc](/home/xclem/projetsperso/agentic-campaign/agentcore-project/UrbanCampaignIntelligencePoc) | lecture structure + métadonnées | `verified_partial` |
| Endpoint sécurisé live | n/a | aucune invocation live | `pending` |
| AgentCore Gateway live | n/a | non branché | `pending` |

---

## 9. Verdict

Le projet est **fort** comme démonstrateur de pensée architecturale, de modélisation agentique et de pragmatisme MVP. Il est déjà convaincant pour expliquer:

- comment découper un problème métier
- comment séparer logique déterministe et arbitrage LLM
- comment préparer une cible AWS crédible sans surconstruire

Le prochain seuil de crédibilité n'est plus documentaire. Il est désormais **opérationnel**:

- montrer un vrai endpoint AWS protégé
- brancher `AgentCore Gateway`
- exécuter un scénario de bout en bout sur la cible

Tant que ces trois points ne sont pas démontrés, le projet reste excellent en cadrage et bon en implémentation locale, mais encore incomplet comme preuve finale de déploiement agentique AWS.
