# API Integration Standards & Guidelines

## Authentication & Authorization
All public API requests must include an `Authorization: Bearer <token>` header.
Tokens expire after 3600 seconds and must be refreshed using OAuth2 client credentials grant.

## Rate Limiting & Throttling
- Standard Tier: 120 req/min with burst allowance of 200.
- Enterprise Tier: 2,000 req/min with burst allowance of 3,500.
Rate limit headers returned:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Error Handling Standards
All APIs must return standardized RFC 7807 problem details in JSON format.
Errors must include `type`, `title`, `status`, `detail`, and `instance`.
