# Production deployment contract

The manually dispatched `Production` workflow is the public, auditable
deployment contract for Baixada Truco. It contains no credentials, private
resource inventory, or licensed files.

Every dispatch verifies the exact protected `main` revision and the complete
public compatibility graph. The `deploy` input defaults to `false`. A real
deployment additionally requires a passing `CI` run for the same revision and
the protected `production` GitHub environment.

## Release construction

The workflow:

1. materializes the exact server and web commits from `stack.lock.json`;
2. obtains short-lived Google credentials through GitHub OIDC;
3. downloads the five licensed runtime cues from private GCS and verifies the
   public byte-size/SHA-256 lock;
4. builds both production containers on the ephemeral runner;
5. pushes them to Artifact Registry and resolves immutable image digests; and
6. deploys those digests to two independent Cloud Run services.

The licensed cues exist only in the web image and the ephemeral build
workspace. They are never committed, cached, or uploaded as Actions artifacts.

## Runtime boundary

`truco-web` is public. `truco-server` requires IAM authentication and accepts
traffic only from the dedicated web runtime identity. The web BFF obtains
short-lived Google identity tokens from the Cloud Run metadata server, so
browser clients never receive the server origin or an invocation credential.

Both services use request-based billing, zero minimum instances, one maximum
instance, fractional CPU, and concurrency one. This preserves the server's
in-memory session model while bounding scale-out.

After deployment, the workflow checks the new `run.app` web origin, creates a
real random-bot match through the BFF, and fetches all five licensed cues. If a
deployment or smoke check fails and a prior revision exists, traffic is
returned to the prior web and server revisions.

Exact project identities, resource names, asset generations, DNS cutover, and
operator rollback procedures remain in the private `baixada-ops` repository.
