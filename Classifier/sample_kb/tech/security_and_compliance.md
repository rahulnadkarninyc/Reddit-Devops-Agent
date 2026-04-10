# Security and Compliance

## Overview

Opsera embeds security and compliance controls directly into the software delivery pipeline rather than treating them as a post-delivery audit function. Engineering teams configure security gates as required pipeline steps; the platform enforces them on every run and logs the evidence. The result is a continuous, auditable record that controls were applied consistently — not just attested to.

This capability matters most to organizations operating under formal compliance frameworks (SOC 2, FedRAMP, HIPAA, PCI-DSS) and to security-conscious engineering orgs that need to demonstrate governance to customers, partners, or regulators.

## Security Gates in Pipelines

Opsera supports configurable **security gates** — pipeline steps that must pass before execution continues to the next stage. If a gate fails, the pipeline halts and the deployment does not proceed. Gates can be configured as:

- **Hard blocks**: pipeline cannot proceed under any condition until the gate passes
- **Soft gates with approval**: pipeline pauses and requires a named approver (security engineer, team lead) to review and explicitly override before continuing
- **Informational**: gate result is logged and surfaced in the dashboard but does not block execution (used for tracking, not enforcement)

Gate configurations are versioned and owned by the platform team, not the individual pipeline author, ensuring they cannot be bypassed by modifying pipeline code.

## SAST and DAST Integration

Opsera integrates with major static and dynamic analysis tools as first-class pipeline steps:

**SAST (Static Application Security Testing)**:
- SonarQube — code quality and vulnerability scanning with configurable quality gate thresholds
- Checkmarx — deep static analysis for security vulnerabilities across multiple languages
- Snyk — dependency vulnerability scanning for open-source packages

**Container and Infrastructure Scanning**:
- Anchore and Aqua Security — image scanning before container deployment
- OWASP Dependency-Check — CVE detection in third-party libraries
- Terraform plan analysis for infrastructure misconfigurations (via Checkov or Terrascan integrations)

Each scan step is configured with a severity threshold. A pipeline step running Snyk can be configured to fail if any `CRITICAL` severity CVE is found, or to warn but continue for `HIGH` severities, depending on team policy.

## Compliance Reporting

Opsera generates compliance evidence reports that map pipeline execution history to the control requirements of specific frameworks:

**SOC 2**: Evidence that change management controls were followed — every production deployment went through defined stages, was approved by authorized personnel, and had associated test and security scan results.

**FedRAMP**: Pipeline audit logs showing that FIPS-compliant tooling was used, access was scoped appropriately, and all deployments to federal environments were authorized and traceable.

**HIPAA / PCI-DSS**: Evidence of access controls, encryption-in-transit validation in deployment steps, and logging of all credential usage.

Reports can be scoped to a time range, a set of pipelines, or a specific environment. They are exportable as PDF or structured JSON for submission to auditors or ingestion into GRC tools.

## Who Cares About This

**Security engineering teams** use Opsera to enforce scanning requirements across all pipelines org-wide, without needing to review and approve each team's pipeline configuration manually.

**Platform engineering teams** use it to publish pipeline templates with security gates pre-embedded, so that new services automatically inherit compliant delivery workflows from day one.

**Compliance and GRC teams** use it to reduce audit prep time. Instead of manually collecting screenshots and log exports across five tools, they pull a single compliance report from Opsera covering the full audit period.

**Engineering leadership** uses it to give security and compliance assurance to customers, partners, and boards without diverting engineering bandwidth to manual evidence collection.
