# Penpot AIO Runtime Notes

The default path uses bundled PostgreSQL, Redis-compatible cache, filesystem asset storage, and Mailpit. Keep those defaults for the simplest Unraid install.

## External Services

Set these only when intentionally moving a service out of the AIO container:

- `PENPOT_AIO_ENABLE_INTERNAL_POSTGRES=false` with `PENPOT_DATABASE_URI`
- `PENPOT_AIO_ENABLE_INTERNAL_REDIS=false` with `PENPOT_REDIS_URI`
- `PENPOT_AIO_ENABLE_MAILPIT=false` with real `PENPOT_SMTP_*`
- `PENPOT_OBJECTS_STORAGE_BACKEND=s3` with S3 bucket, endpoint, and credentials

## Production Exposure

For HTTPS/public use:

- set `PENPOT_PUBLIC_URI` to the real HTTPS URL
- remove `disable-secure-session-cookies`
- remove `disable-email-verification` unless you have a deliberate reason
- configure real SMTP
- review SSRF and OAuth/OIDC/LDAP settings before allowing untrusted users

## Generated Values

Generated values live in `/appdata/config/generated.env`. Explicit template variables override generated values. `/appdata/config/extra.env` loads last for rare emergency overrides.
