# Domain glossary

## Dependency drift

A repository's declared SDK version is behind the version observed from its
configured registry feed. Drift is a dependency-level fact; it does not imply
that any particular source call is broken.

## Automatic dependency update

A patch or minor dependency drift whose version constraints can be rewritten
unambiguously. It may proceed through the normal verification and PR flow.

## Vetted migration

A documented, provider-specific API migration with a concrete old and new
call shape. Major-version drift is reported and planned, but is only applied
when it is paired with a vetted migration.
