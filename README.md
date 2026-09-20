# StormPilot

**Crash-test a stormwater control plan before relying on it.**

StormPilot is a simulation-backed workbench for finding, explaining and replaying failures in a control policy. It uses public benchmark networks and the EPA SWMM engine. Its result is an inspectable experiment: the tested assumptions, a reduced failure example, a comparison with another policy and the files needed to replay it.

Development is underway for NextStep Hacks 2026, Earth Forward. This repository is private. A simulated outcome is not evidence that a real neighborhood is protected.

## Working documents

- [Implementation plan](docs/implementation-plan.md)
- [Product and design direction](docs/design-direction.md)
- Scientific validation and product review documents are being developed alongside the engine.

## Intended workflow

1. Choose a published network, a documented control policy and a measurable requirement.
2. Run the nominal case and a declared range of instrumentation faults.
3. Investigate a failure and remove unnecessary conditions through reruns.
4. Compare another policy under matched rainfall and exogenous fault/noise conditions.
5. Export and independently validate a replayable evidence packet.

Numerical outcomes come from the simulator. Model provenance, actual units, evaluation boundaries and unresolved failures remain visible. No demo improvement is assumed before execution.

## Attribution

- [EPA Storm Water Management Model](https://www.epa.gov/water-research/storm-water-management-model-swmm)
- [pystorms](https://github.com/kLabUM/pystorms), public stormwater control benchmarks and models. Any included GPL-licensed material retains its notices.

See source manifests beside curated model files for exact revisions and licenses. Setup, execution and replay instructions will be added as their commands are verified.

