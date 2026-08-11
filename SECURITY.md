# Security policy

Do not include secrets, session cookies, private API keys, bearer tokens, or
personal data in source manifests. Use environment-backed wrapper commands when
credentials are legitimately required. Never commit downloaded collections or
the Sweeper workspace to Git.

Contact information is personal data in many contexts. Only process phone or
email datasets with a documented lawful basis, purpose limitation, retention
policy, access controls, and any required consent or notice. Do not use Sweeper
V2 to assemble spam, surveillance, harassment, or doxxing datasets.

Before deploying Sweeper V2:

- verify the source and every redirect;
- use provider-approved APIs or bulk endpoints;
- restrict network egress when processing sensitive institutional material;
- set maximum object sizes and storage quotas;
- scan downloaded content before passing it to downstream software;
- keep AI review disabled for confidential or regulated material unless an
  approved data-processing arrangement exists; and
- run the process as an unprivileged user in a dedicated workspace.

Please report vulnerabilities privately to the repository owner through
GitHub's private vulnerability reporting feature. Do not include live secrets
or sensitive downloaded data in a report.
