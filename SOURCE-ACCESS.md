# Code access for judges

The repository is private: https://github.com/sudo-anshul/stormpilot. A private repository URL alone does not give a judge access. The local source ZIP has not been uploaded or shared with judges; no judge invitation has been sent.

The accompanying local **stormpilot-source.zip** is a compact code handoff built from the final recorded Git commit. `SOURCE-MANIFEST.json` inside the ZIP identifies that commit and lists every included file's SHA-256. The ZIP contains the app, Python service, pinned native solver, independent validator, evaluation code, build configuration, licenses, recorded welcome fixture and compact evaluation reports.

It excludes credentials, local account metadata, Git history, installed dependencies, generated builds, runtime job data, scratch files and large full-proof archives. The separate evidence archives retain the complete historical traces. Their paths in compact reports are references to those separate artifacts; this code ZIP alone cannot establish historical trace checks that require them.

## Choose an explicit handoff

1. **Share the code ZIP.** Upload it to storage you control, grant the contest's judges viewing/download access, and place that working link in the submission's code field. Open the link using an account or browser session with the same access as a judge. Keep the link available throughout judging. Sharing the ZIP is a separate action; its local creation does not grant access.
2. **Grant private repository access.** Obtain the judges' required GitHub accounts through the contest's stated process, explicitly invite them to the private repository, and provide its URL. Confirm that they can view the source. Do not make the repository public as an implicit workaround.

Either route needs the entrant's explicit action. A live demo link or an expiring experiment-export URL does not by itself provide stable access to the complete app code.

## Run the code locally

Extract the ZIP and enter its `stormpilot/` directory. Follow `README.md` to install Node dependencies, build the frontend and start the local Python server. Local execution requires Python, Node and a C compiler; it does not require a Vercel account or Blob credential. `npm test` runs the included test suites.

The licenses and third-party notices remain included. The frozen reports preserve both rejected controller evaluations; access to the code does not change those results or establish field safety.
