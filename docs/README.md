# Documentation Map

Ce dossier regroupe la documentation opérationnelle, d'architecture et d'audit du projet.

Règle de lecture :

- `README.md` à la racine = point d'entrée rapide
- `docs/README.md` = index documentaire
- `docs/STATUS.md` = état réel et priorités
- `roadmap.md` = ordre d'exécution et vision

---

## 1. Core

Documents à lire en premier pour comprendre le MVP.

| Document | Rôle | Statut |
|---|---|---|
| [../README.md](/home/xclem/projetsperso/agentic-campaign/README.md) | vue d'ensemble rapide, exécution locale, liens utiles | canonique |
| [../ARCHITECTURE.md](/home/xclem/projetsperso/agentic-campaign/ARCHITECTURE.md) | architecture cible, patterns agentiques, split déterministe / LLM | canonique |
| [../Urban_Campaign_Intelligence_PRD_MVP.md](/home/xclem/projetsperso/agentic-campaign/Urban_Campaign_Intelligence_PRD_MVP.md) | cadrage initial MVP | cadrage initial |
| [../roadmap.md](/home/xclem/projetsperso/agentic-campaign/roadmap.md) | lots, priorités, critères de sortie | canonique |
| [STATUS.md](/home/xclem/projetsperso/agentic-campaign/docs/STATUS.md) | état réel du repo, prochaines actions, blocages | canonique |
| [DECISIONS.md](/home/xclem/projetsperso/agentic-campaign/docs/DECISIONS.md) | décisions structurantes / ADRs courtes | canonique |

---

## 2. AWS / Delivery

Documents utiles pour comprendre ou exécuter le Lot 2.

| Document | Rôle | Statut |
|---|---|---|
| [LOT2_INFRA_MVP.md](/home/xclem/projetsperso/agentic-campaign/docs/LOT2_INFRA_MVP.md) | cible infra MVP AWS et arbitrages | canonique |
| [GATEWAY_TOOLS.md](/home/xclem/projetsperso/agentic-campaign/docs/GATEWAY_TOOLS.md) | contrats tools et pattern providers/fallback | référence technique |

---

## 3. Diagrams

| Document | Rôle |
|---|---|
| [diagrams/README.md](/home/xclem/projetsperso/agentic-campaign/docs/diagrams/README.md) | inventaire des schémas canoniques et historiques |

Règle :

- privilégier les schémas explicitement marqués comme canoniques
- considérer les anciens schémas comme support historique, pas comme source de vérité

---

## 4. Audit / Historical Review

Ces documents sont utiles pour relire le projet ou préparer un entretien, mais ils ne doivent pas devenir la source principale de vérité.

| Document | Rôle | Statut |
|---|---|---|
| [AUDIT_GLOBAL_PROJET.md](/home/xclem/projetsperso/agentic-campaign/docs/AUDIT_GLOBAL_PROJET.md) | audit global architecture / delivery / doc | audit ponctuel |

Usage recommandé :

- les lire pour la synthèse, les risques et la préparation d'entretien
- ne pas les utiliser comme documents canoniques si `README.md`, `STATUS.md`, `ARCHITECTURE.md` ou `roadmap.md` disent autre chose
