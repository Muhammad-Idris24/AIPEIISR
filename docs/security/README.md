# Security

Development accepts `x-role` only while `X_ROLE_ENABLED=true`. When it is false, the backend strips caller-supplied role headers and accepts privileged role binding only from a verified HS256 Bearer token. The current token issuer remains a local-development scaffold; production still requires a user directory or external OIDC provider, MFA, CSRF/CORS policy, secret management, upload malware scanning, SSRF controls and retention policy.
