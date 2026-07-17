# Gateway Tools

## Objectif

Définir les contrats des tools Gateway avant de brancher de vraies sources externes.

Le principe est le suivant :

- les `tools` récupèrent ou exposent des données brutes
- les `agents` interprètent ces données en signaux métier
- le moteur métier reste stable quand on remplace un backend mock par une vraie source
- un agent peut optionnellement utiliser un LLM sans changer le contrat du tool

Le `Review Agent` suit la même logique, même s'il ne consomme pas directement un tool externe.

---

## Tools ciblés

- `get_weather`
- `get_events`
- `get_mobility`
- `get_zones`
- `get_advertisers`

Pour cette étape, seuls les trois premiers sont formalisés explicitement.

Le contrat d'exemple machine-readable est disponible ici :

- [tools/gateway_tool_contracts.json](/home/xclem/projetsperso/agentic-campaign/tools/gateway_tool_contracts.json)

---

## Design rules

- entrée minimale : `city`, `datetime`
- sortie brute mais structurée
- aucun raisonnement métier dans les tools
- aucune justification LLM dans les tools
- un agent peut ensuite enrichir, interpréter et normaliser

---

## Tool to Agent mapping

| Tool | Consommé par | Rôle agent |
|---|---|---|
| `get_weather` | `Weather Agent` | convertir météo brute en impact contextuel |
| `get_events` | `Events Agent` | convertir événements bruts en pression de trafic et signaux métier |
| `get_mobility` | `Mobility Agent` | convertir état réseau brut en impact mobilité |

---

## État actuel

- provider mock local implémenté dans `src/urban_campaign_intelligence/gateway_tools.py`
- provider météo semi-réel `Open-Meteo` implémenté avec fallback vers le mock
- scénarios fake plus riches supportés côté mock pour `weather`, `mobility` et `events`
- agents locaux refactorés pour consommer des payloads de type Gateway
- backends réels non branchés

Configuration actuelle :

- `WEATHER_PROVIDER=mock`
- `WEATHER_PROVIDER=open_meteo`
- `EVENTS_PROVIDER=mock`
- `EVENTS_PROVIDER=paris_open_data`
- `MOBILITY_PROVIDER=forecast`
- `MOBILITY_PROVIDER=mock`

Quand `open_meteo` est activé :

- la ville est résolue via la Geocoding API
- la météo est récupérée via Open-Meteo
- si l'appel échoue, le système revient sur le mock sans casser le run

Quand `paris_open_data` est activé :

- les événements sont recherchés via le dataset `Que faire à Paris ?`
- la recherche est pilotée par mots-clés selon le type d'événement cible
- si l'appel échoue ou ne retourne rien d'exploitable, le système revient sur le mock

Quand `forecast` est activé :

- la mobilité est estimée à partir d'un profil moyen `day_of_week + hour`
- le provider retourne un état réseau prévisionnel simple pour le planning
- la logique reste déterministe et explicable

---

## Étape suivante recommandée

1. observer le comportement `open_meteo` sur plusieurs scénarios
2. conserver strictement le même contrat de sortie
3. ne pas modifier les agents tant que le contrat est respecté
4. observer le comportement `forecast` sur plusieurs scénarios
5. conserver strictement le même contrat de sortie
6. enrichir l'arbitrage métier entre annonceurs avant de multiplier les providers
