# Generated API contracts

This directory is generated from `contracts/openapi.json` by the frontend command:

```powershell
Set-Location frontend
npm run contract:generate
```

The same generated declaration is copied to `frontend/src/api/generated/schema.d.ts` for the
frontend build context. Do not edit either generated declaration manually. Run
`npm run contract:check` to detect missing or stale output.

The declaration files are intentionally absent until the OpenAPI generator and frontend
dependencies can run successfully; see the Phase 1 test report for the current blocker.
