# DORA Metrics

## Overview

Opsera measures all four DORA (DevOps Research and Assessment) metrics — Deployment Frequency, Lead Time for Changes, Change Failure Rate, and Mean Time to Recovery — by aggregating data directly from the tools in an organization's existing toolchain. No manual data entry, no spreadsheet exports. The metrics are computed from live, source-of-truth data.

Engineering leaders use these dashboards to identify process bottlenecks, benchmark team performance over time, and report software delivery health to executive stakeholders.

## Data Collection

Opsera pulls DORA metric data from connected tools using its integration layer:

- **Deployment events** come from CI/CD tools (Jenkins, GitHub Actions, GitLab CI) and deployment targets (Kubernetes, AWS CodeDeploy, Harness, Spinnaker). A "deployment" is defined as a successful execution of a deploy step to a production or production-equivalent environment.
- **Commit and PR data** comes from source control systems (GitHub, GitLab, Bitbucket) and is used to calculate Lead Time — the elapsed time from first commit to production deployment.
- **Incident and failure data** comes from incident management tools (PagerDuty, OpsGenie) and ticketing systems (Jira, ServiceNow) to calculate Change Failure Rate and MTTR.

Opsera normalizes these signals across tools and applies configurable rules to define what counts as a production environment, what constitutes a "failure," and how work items map to deployments.

## The Four Metrics

**Deployment Frequency**: How often a team deploys to production. Opsera surfaces this at team, service, and org level, with trend lines over 7/30/90-day windows. Teams can filter by environment, pipeline, or repository.

**Lead Time for Changes**: The time from a commit being merged to that commit reaching production. Opsera traces the full commit-to-deploy chain across source control and CI/CD tools, calculating median and 95th-percentile lead times.

**Change Failure Rate**: The percentage of deployments that result in a degraded production state requiring a hotfix, rollback, or incident. Opsera correlates deployment events with incident records to compute this automatically.

**Mean Time to Recovery (MTTR)**: How long it takes to restore service after a failure. Calculated as the time between incident creation and resolution, linked to the affected service and deployment.

## Dashboards and Views

The DORA dashboard provides:

- **Executive summary view**: A single-screen snapshot of all four metrics vs. DORA performance bands (Elite, High, Medium, Low), designed for board-level or all-hands reporting.
- **Team-level drill-down**: Individual team scorecards showing metric trends, with the ability to compare teams or filter by service area.
- **Pipeline attribution**: Tracing which specific pipelines or repositories are contributing to failures or long lead times.
- **Trend analysis**: Week-over-week and quarter-over-quarter views to surface whether initiatives (new tools, process changes) are moving metrics in the right direction.

## How Leaders Use It

Engineering leaders use DORA dashboards in several recurring workflows:

- **Engineering reviews**: Monthly or quarterly reviews where VPs of Engineering present delivery performance to peers or the CEO.
- **Bottleneck identification**: When lead time increases, drill-down views help attribute the slowdown to a specific team, pipeline stage, or tool integration.
- **Incident retrospectives**: MTTR data tied to specific deployments and teams informs where reliability improvements are most needed.
- **Headcount and tooling decisions**: Sustained low deployment frequency in a team can be a signal of tooling debt, team capacity issues, or process overhead worth investigating.
