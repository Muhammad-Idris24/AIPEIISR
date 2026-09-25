# Technical Research

Verified 2026-09-22 from official documentation:

- Wikimedia MediaWiki REST API supports JSON/HTML access to Wikimedia content and page history; use only compliant, attributed requests. https://www.mediawiki.org/wiki/API:REST_API
- Hugging Face Inference Providers offers routed inference and documents $0.10 monthly free-user credits, subject to change. It is useful for experiments, not a dependable always-on zero-cost production dependency. https://huggingface.co/docs/inference-providers/pricing
- Ollama exposes a local HTTP API, suitable as an optional local-provider adapter where a host can run models. https://docs.ollama.com/api
- GDELT and specific partner feeds require source-specific terms/quota verification before enabling production collectors. **OPEN DECISION**: approved source register.

Implementation decision: ship deterministic mock providers for the complete development/test loop; provider interfaces allow Ollama or Hugging Face configuration later. No pricing, availability, Nigerian availability or retention claim is made without provider/account verification.

## Authentication update — 2026-09-24

- Auth0 supports adding a user's assigned roles from `event.authorization.roles`
  to a namespaced custom claim in an access token using a Post-Login Action.
  AIPEIISR uses `https://api.aipeiisr.local/roles` and validates only the
  access token server-side. https://support.auth0.com/center/s/article/add-roles-and-permissions-to-the-id-token-using-actions
- Auth0 API RBAC can include a user's permissions in the access-token
  `permissions` claim when both RBAC and "Add Permissions in the Access
  Token" are enabled. The initial integration authorizes platform roles; a
  later fine-grained-permission mapping remains a hardening task.
  https://support.auth0.com/center/s/article/Adding-RBAC-Permissions-to-Access-Tokens
