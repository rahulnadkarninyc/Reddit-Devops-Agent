# Pipeline Orchestration

## Overview

Opsera's no-code pipeline orchestration engine lets teams design, deploy, and manage CI/CD workflows through a visual interface — without writing infrastructure glue code. Engineers select tools from a library of pre-built integrations (Jenkins, GitHub Actions, Terraform, SonarQube, Anchore, Twistlock, and others), configure their parameters, and connect them in a directed workflow graph. Opsera handles the underlying API calls, credential management, and execution sequencing.

The result is a pipeline that is reproducible, auditable, and modifiable without touching YAML or Groovy scripts.

## How It Works

Pipelines are built from **workflow steps**, each representing an action in a connected tool:

- **Source control steps**: clone a repo, trigger on push/PR events from GitHub, GitLab, or Bitbucket
- **Build steps**: invoke a Jenkins job, run a GitHub Actions workflow, or execute a Maven/Gradle build
- **Test steps**: run unit tests, integration tests, or quality gate checks via SonarQube
- **Security steps**: trigger SAST scans (Sonar, Checkmarx), dependency checks (Snyk, OWASP), or container scans (Anchore)
- **Deploy steps**: apply Terraform plans, deploy to Kubernetes clusters, or push to AWS/Azure/GCP environments
- **Notification steps**: post results to Slack, create Jira tickets on failure, or update ServiceNow change records

Steps are arranged in a visual DAG (directed acyclic graph) editor. Conditional branching, parallel execution paths, and approval gates can be inserted between steps without code. Each step's configuration is stored as a versioned record — changes are tracked, diffable, and rollback-able.

## Pain Points It Solves

**Glue code sprawl**: In most organizations, CI/CD pipelines accumulate custom shell scripts and wrapper code that no one fully owns. When the engineer who wrote the pipeline leaves, the org is left with undocumented automation. Opsera replaces that with declarative, UI-configured workflows that any team member can inspect and modify.

**Inconsistent standards across teams**: Platform teams frequently struggle to enforce pipeline standards (required security scans, mandatory quality gates, approval steps) across dozens of product squads. Opsera supports **pipeline templates** — reusable, organization-approved workflow patterns that can be published and enforced org-wide while still allowing per-project parameterization.

**Tool migration friction**: When an org moves from Jenkins to GitHub Actions, or adds Terraform to an existing workflow, re-wiring pipelines is labor-intensive. Because Opsera abstracts the tool layer, swapping or adding a step is a configuration change rather than a code rewrite.

**Audit readiness**: Opsera logs every pipeline execution with full step-level detail — what ran, what the inputs and outputs were, which credentials were used, and what the outcome was. This execution history is queryable and exportable, which significantly reduces the manual effort involved in audit prep.

## Reusable Templates

Platform teams can publish **pipeline blueprints** — parameterized templates for common delivery patterns (e.g., "Java microservice to EKS", "Terraform infrastructure change with approval gate"). Product squads instantiate these templates and fill in project-specific values. This allows centralized governance without centralized execution bottlenecks.
