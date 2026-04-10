# Tool Chain Integration

## Overview

Opsera connects to 20+ DevOps tools through a managed integration layer that handles authentication, API normalization, and data synchronization. The goal is to give engineering organizations a single operational view across their entire software delivery toolchain — without requiring them to standardize on any particular set of tools.

Integrations are configured through the Opsera UI. Credentials are stored encrypted, connections are tested at setup, and sync frequency is configurable per integration. Most integrations are available within minutes of connecting.

## Supported Tool Categories

**Source Control**: GitHub, GitLab, Bitbucket, Azure DevOps Repos  
**CI/CD Execution**: Jenkins, GitHub Actions, GitLab CI, CircleCI, TeamCity, Azure Pipelines  
**Artifact Management**: JFrog Artifactory, Nexus, AWS ECR, Docker Hub  
**Infrastructure as Code**: Terraform (with state backend support for S3, Terraform Cloud), Ansible, AWS CloudFormation  
**Security Scanning**: SonarQube, Checkmarx, Snyk, Anchore, Aqua Security, OWASP Dependency-Check  
**Cloud Platforms**: AWS, Azure, GCP (deployment targets and resource inventory)  
**Ticketing and Change Management**: Jira, ServiceNow, Linear  
**Incident Management**: PagerDuty, OpsGenie  
**Monitoring**: Datadog, New Relic, Dynatrace (used for MTTR correlation)  
**Notification**: Slack, Microsoft Teams, email

## How Data Normalization Works

Each tool exposes data through its own schema and API conventions. A "deployment" in Jenkins looks structurally different from a "release" in GitHub Actions or a "run" in CircleCI. Opsera maps these tool-specific concepts to a normalized internal data model that includes:

- **Pipeline Run**: a single execution of a delivery workflow, with status, timestamps, environment target, and triggering event
- **Change**: a code commit or PR, linked to a pipeline run and a work item
- **Deployment Event**: a production-environment pipeline run, used to compute DORA metrics
- **Incident**: a failure event from an incident management tool, correlated to a deployment

This normalized layer is what powers cross-tool analytics. When a VP looks at lead time, they're seeing a metric computed across GitHub PR data, Jenkins build history, and Kubernetes deploy records — unified through Opsera's data model.

## Common Integration Pain Points Solved

**"We can't get a single view of what's in production"**: When deployment data lives in five different CI/CD tools and three cloud consoles, there's no reliable answer to "what version of service X is running in prod right now?" Opsera's deployment event model provides a unified deployment registry across tools.

**"Every team's pipeline is different, and we can't enforce standards"**: Because Opsera sits above the CI/CD layer, it can apply consistent pre/post conditions (security scans, approval gates) to pipelines regardless of which underlying tool is executing them.

**"Connecting a new tool breaks everything downstream"**: Opsera's integration model is additive — connecting a new tool enriches the existing data model rather than requiring reconfiguration. Adding Snyk to an existing pipeline with GitHub and Jenkins does not require changes to the GitHub or Jenkins integrations.

**"Audit prep takes two weeks"**: Compliance auditors typically need evidence that specific controls were applied to all production deployments during an audit period. Because Opsera logs all pipeline executions with tool, step, credential, and outcome data in a normalized format, generating this evidence is a query rather than a manual process.

## Credential and Access Management

Opsera supports OAuth 2.0, API token, SSH key, and service account authentication methods depending on the tool. Credentials are encrypted at rest and accessed via Opsera's secrets manager. Teams can scope tool connections to specific projects or repositories, and connection health is monitored with alerting on auth failures or API rate limit breaches.
