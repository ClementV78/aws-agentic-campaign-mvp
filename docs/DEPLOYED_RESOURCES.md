# Ressources AWS déployées

Inventaire des ressources créées par `scripts/deploy.sh` pour le MVP Urban Campaign Intelligence.
Source de vérité machine : [`outputs/deploy/deploy-outputs.json`](../outputs/deploy/deploy-outputs.json)
et [`outputs/deploy/agentcore-status.txt`](../outputs/deploy/agentcore-status.txt). Ce document en est
la lecture humaine.

| | |
|---|---|
| **Compte** | `194031983377` |
| **Région** | `us-east-1` |
| **Profil AWS** | `aws100demo1` (⚠️ ne pas utiliser `CloudRadarTerraformUser`, autre compte) |
| **Stade** | `poc` |

## Stack CloudFormation — `AgentCore-UrbanCampaignIntelPoc-default`

Créé par `agentcore deploy` (couche CDK, `managedBy: CDK`).

| Ressource | Type | Identifiant physique |
|---|---|---|
| **AgentCore Runtime** | `AWS::BedrockAgentCore::Runtime` | `UrbanCampaignIntelPoc_UrbanCampaignIntelPoc-9WdEB7BnPP` |
| Rôle d'exécution | `AWS::IAM::Role` | `AgentCore-UrbanCampaignIn-ApplicationAgentUrbanCamp-GQ80kMY4QQKk` |
| Policy du rôle | `AWS::IAM::Policy` | `Agent-Appli-IMmdDMNDhXW8` |

- **Runtime ARN** : `arn:aws:bedrock-agentcore:us-east-1:194031983377:runtime/UrbanCampaignIntelPoc_UrbanCampaignIntelPoc-9WdEB7BnPP`
- C'est la ressource comptée par le quota `AWS::BedrockAgentCore::Runtime` (`maxAgents`).
- Le rôle d'exécution porte l'accès `bedrock:InvokeModel` (Nova Lite) utilisé par l'agent.

## Hors stack

| Ressource | Identifiant | Créé par |
|---|---|---|
| **Bucket S3** (artefacts de replay) | `urban-campaign-intelligence-poc-194031983377-us-east-1` | `deploy.sh` (durci : public-access-block, chiffrement AES256, versioning, BucketOwnerEnforced) |
| Objets S3 | `deploy/deploy-artifacts.zip`, `deploy/deployment-manifest.json` | `deploy.sh` |
| **CloudWatch Log Group** | `/aws/bedrock-agentcore/runtimes/UrbanCampaignIntelPoc_UrbanCampaignIntelPoc-9WdEB7BnPP-DEFAULT` | créé au premier démarrage du runtime |

## Préexistant, réutilisé (non créé par ce déploiement)

- **Bootstrap CDK** (`CDKToolkit`, version 32) : bucket d'assets, ECR, rôles, param SSM.
- **Pas** d'ECR applicatif ni d'image (CodeZip ≠ conteneur), **pas** de CodeBuild, **pas** d'API Gateway,
  **pas** de Gateway / Memory / Payments (capacités non câblées à ce stade).

## Utiliser le runtime déployé

Invocation (prompt-first — mettre une ville dans le prompt) :

```bash
cd agentcore-project/UrbanCampaignIntelligencePoc
AWS_PROFILE=aws100demo1 AWS_REGION=us-east-1 \
  agentcore invoke "Plan a Nike ad campaign in Paris this Saturday afternoon" --target default
```

Logs du runtime :

```bash
AWS_PROFILE=aws100demo1 AWS_REGION=us-east-1 \
  aws logs tail /aws/bedrock-agentcore/runtimes/UrbanCampaignIntelPoc_UrbanCampaignIntelPoc-9WdEB7BnPP-DEFAULT --since 10m --follow
```

## Teardown

`scripts/destroy.sh` (piloté par `outputs/deploy/deploy-outputs.json`) : supprime le runtime/stack
AgentCore via CDK puis nettoie le bucket S3. Voir [RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md).

---

_Régénérer cet inventaire :_
`aws cloudformation describe-stack-resources --stack-name AgentCore-UrbanCampaignIntelPoc-default`
(profil `aws100demo1`, région `us-east-1`).
