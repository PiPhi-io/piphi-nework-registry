# Contributing

Thanks for helping grow the PiPhi ecosystem.

This repository is the curated public registry consumed by the PiPhi Registry API. Not every submitted integration is published automatically. The ecosystem is open to developers, but the public catalog is reviewed before publication.

## Submission Flow

1. Open the `Submit Integration` issue form.
2. Provide the repository URL, manifest path, metadata, and support contact.
3. GitHub Actions validates the submission automatically.
4. If validation passes, the submission moves to human review.
5. Once approved, automation proposes a ready-to-paste registry entry.
6. Approved submissions are added to `registry.json`.

Review guidance for maintainers lives in [REVIEWING.md](./REVIEWING.md).

## What Reviewers Look For

- Does it work as described?
- Is it safe to surface in the public catalog?
- Is the UX understandable for users?
- Are the claims honest and supportable?

Submissions that pass automation should be labeled `ready-for-review` before a maintainer makes an approval decision.

## Before You Submit

- Make sure your integration repository is public.
- Make sure the manifest is present and current.
- Make sure the integration ID is stable.
- Include a clear name and short description.
- Include a support contact.
- Provide an icon URL if available.
- Be honest about elevated runtime requirements such as privileged mode, USB access, or host mounts.

## Approval Notes

Passing automated checks does not guarantee approval. Some submissions will require manual review or testing, especially for:

- sidecars and platform services
- hardware integrations
- privileged or host-networked runtimes
- first-time publishers

## Automated Validation

Current automated checks include:

- repository URL format and accessibility
- manifest path existence
- manifest JSON fetch and parse
- duplicate integration ID detection against `registry.json`
- basic metadata consistency checks between the submission and manifest
- icon URL reachability when provided

## Registry Contract

Approved entries are stored in `registry.json`.

Current catalog fields include:

- `id`
- `name`
- `version`
- `type`
- `deployment_mode`
- `trust_level`
- `risk_level`
- `description`
- `platforms`
- `image`
- `icon_url`
- `banner_url`
- `repo_url`
- `manifest_path`
- `runtime_requirements`

## Support

If you are unsure whether your integration is ready, open a submission issue anyway and include testing notes. That gives reviewers enough context to help you move it forward.
