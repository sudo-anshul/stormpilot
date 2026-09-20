# Vercel deployment

Live app: **https://stormpilot.vercel.app**. The source repository remains private.

## Runtime

`Dockerfile.vercel` builds the React app with Node, compiles the pinned EPA SWMM C source on Linux, and runs the Python service as a non-root user. `vercel.json` routes the app to Vercel's native container service. This is a native backend deployment; a static frontend alone cannot execute the solver.

`cloud_server.py` runs native work inside the active HTTP request, then persists completed artifacts before returning. The browser can wait on that request and retrieve immutable status/result links afterward. Inputs, search calls, worker concurrency and timeouts are bounded. A platform timeout still interrupts the request; very large supported searches may not fit the hosting request limit.

A private Vercel Blob store holds job workspaces, evidence archives, imported models and completion manifests. Completion is published after required artifacts. Result retrieval restores compact state; replay/repair/evaluation restore the required full workspace. Large exports redirect to scoped, five-minute signed download URLs. Treat shared result IDs and download links as access capabilities: this prototype has no user account or per-user authorization layer. Do not use it for confidential municipal models.

## Rebuild and redeploy

The existing Vercel project is linked in ignored `.vercel/` metadata. The Blob credential is supplied by Vercel and optionally kept in ignored `.env.local` for local cloud-adapter checks. Do not put credentials in source or frontend variables.

```sh
npm test
npm run build
npx --yes vercel@59.23.2 deploy --prod --yes
```

The ordinary local path remains `python3 server.py --port 8787` and needs no Blob credential. `cloud_server.py` is the hosting adapter, not a requirement for local reproduction.

## Execution evidence and limits

Vercel successfully compiled and executed SWMM on Linux. The first production smoke job was `8490cd47a9444985`; its native metrics matched the corresponding Mac example. The final release has a separate recorded verification entry in `docs/verification.md`.

GitHub Actions is configured, but GitHub refused to start its runners because of account billing. No GitHub-hosted CI pass is claimed. Vercel's actual Linux build and native runs supply separate platform evidence. No payment settings were changed.

Durable storage is not an unlimited retention promise. The app is a bounded public demonstration with no operator validation, authentication, usage accounting or production service-level guarantee. Expiring export URLs can be refreshed from the corresponding job's export action.
