# Use a model you own

Choose **Import model** in the workbench and select a self-contained UTF-8 SWMM
`.inp` file. Inspect the extracted units, horizon, storage nodes and outlets. Then
choose the link where downstream flow is measured and enter its flow threshold
in **m³/s**, regardless of the model's native flow units.

By default, the configured total flow threshold is divided equally between all
controlled outlets. This is an explicit starting assumption, not a calibrated
control plan. Expand outlet targets to set each target in m³/s before registering
the model. Policy target scale and balancing parameters can then be tested.

Registration fixes the original input and mapping to a content-derived identity.
Each experiment embeds that input and the mapping in its replay request. The ZIP
export includes the original `.inp` file, its hash, the model-specific targets,
solver source and validation/replay tools. A replay needs no model registry or
network connection.

## Supported scope

- File size up to 256 KiB; horizon greater than zero and at most 168 hours.
- DYNWAVE routing, DEPTH offsets and a single SWMM solver thread.
- Up to 200 nodes, 500 links and 200 subcatchments.
- One to 40 rectangular, zero-offset BOTTOM orifices originating at positive-depth
  storage nodes. These outlets are controlled by the selected policy.
- Rainfall stored in inline TIMESERIES and referenced by the model's rain gauges.
- Native CFS, GPM, MGD, CMS, LPS or MLD units. Results and all workbench inputs
  use metres, seconds, m³ and m³/s.

External files, hotstarts, arbitrary control rules, pumps, weirs, groundwater,
quality and other unsupported sections are rejected before native execution.
The structural inspection does not replace SWMM's hydraulic validation; native
input errors appear as a failed experiment with a concrete error message.

This is a single-user workbench. Uploaded inputs are stored on this server and
included in downloaded evidence. Model ownership, calibration and field validity
remain the user's responsibility. Imported simulations establish no field
performance or flood-protection guarantee.
