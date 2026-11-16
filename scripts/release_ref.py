from __future__ import annotations


def accepted_release_refs(registry_id: str, version: str) -> tuple[str, ...]:
    return (
        f"v{version}",
        f"apps/{registry_id}/v{version}",
    )


def require_release_ref(ref: str, *, registry_id: str, version: str) -> None:
    accepted = accepted_release_refs(registry_id, version)
    if ref not in accepted:
        choices = " or ".join(f"'{value}'" for value in accepted)
        raise ValueError(
            f"Release ref '{ref}' does not match {registry_id} version {version}; "
            f"expected {choices}."
        )
