# Reviewing Submissions

This document explains how to review a submission after automated validation has passed.

The goal is to keep the PiPhi ecosystem open to builders while keeping the public registry curated and trustworthy.

## Review States

Suggested issue labels:

- `submission`
- `validation-passed`
- `needs-changes`
- `ready-for-review`
- `approved`
- `rejected`

## Trust and Risk

Reviewers should set trust and risk metadata intentionally.

### Trust Levels

- `official`
  Maintained directly by PiPhi or a clearly official PiPhi publisher.
- `verified`
  Reviewed and approved with strong confidence, but not an official PiPhi package.
- `community`
  Approved for listing, but primarily community-maintained.
- `experimental`
  Listed with limited confidence or early-stage support expectations.

### Risk Levels

- `low`
  No unusual privileges or notable runtime sensitivity.
- `moderate`
  Uses secrets, sidecar behavior, or direct hardware access without broader host privileges.
- `high`
  Uses privileged containers, host networking, broad mounts, or similarly sensitive runtime behavior.

## Review Outcomes

Use one of these outcomes for each submission:

- `approved`
  The integration is suitable for inclusion in the public registry.
- `needs changes`
  The integration may be acceptable, but metadata, UX, trust, or technical issues need to be addressed first.
- `rejected`
  The integration should not be published in the public registry in its current form.

## Reviewer Checklist

Reviewers should answer the following questions.

### 1. Does It Work?

- Does the submission match the actual repository and manifest?
- Does the manifest look internally consistent?
- Are the supported platforms believable from the manifest and repository?
- Are the claimed runtime model and deployment mode accurate?
- Does the integration appear installable and operable in PiPhi?

### 2. Is It Safe?

- Does it request elevated permissions such as:
  - privileged mode
  - host networking
  - USB or device access
  - host filesystem mounts
- Are those permissions justified?
- Does it appear to handle secrets responsibly?
- Does the repository appear trustworthy and maintained?
- Are there any obvious red flags in docs, metadata, or runtime requirements?
- Is the chosen `risk_level` accurate for the runtime requirements?

### 3. Is The UX Understandable?

- Is the integration name clear?
- Is the short description understandable to a normal user?
- Are config requirements explained well enough?
- Are the icon and metadata appropriate for the app-store experience?
- Would a user know what this integration is for before installing it?

### 4. Are The Claims Honest?

- Do the supported platforms match the repo and manifest?
- Is any "official" branding justified?
- Are capability or device support claims believable?
- Does the repository description align with the submitted description?
- Is anything overstated, vague, or misleading?

## When Human Testing Is Recommended

Human pull-down and testing is especially recommended for:

- first-time publishers
- sidecars and platform services
- hardware integrations
- privileged or host-networked runtimes
- integrations with unclear or unusually broad claims

## Suggested Reviewer Comment

Use a concise comment structure like this:

```md
## Review Result

- Outcome: approved | needs changes | rejected
- Works as described: yes | no | unclear
- Safety review: pass | concerns | fail
- UX clarity: good | needs work
- Claims verified: yes | partially | no

### Notes
- ...
- ...
```

## Publication

Once approved:

1. Apply the `approved` label after validation has already passed.
2. Use the generated registry entry comment produced by automation.
3. Add or update the entry in `registry.json`.
4. Confirm icon and artwork URLs are correct.
5. Set `trust_level`, `risk_level`, and `runtime_requirements` intentionally.
6. Verify the final metadata matches the approved submission.
7. Merge the change into the public registry.
