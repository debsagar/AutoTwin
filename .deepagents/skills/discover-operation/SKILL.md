---
name: discover-operation
description: Investigate a selected operational dataset before simulation. Use for process discovery or as intake for an authorized Stage 1 task.
---

# Discover the operation

1. Locate the selected data and read its source description. Identify the case,
   activity, timestamp and resource fields. A case can be an order item rather
   than a whole order. Do not force snapshots into an event log.
2. For XES, use `inspect_log_scope` for full-log coverage and categories, and
   `discover_process` for an exploratory file-prefix overview. The prefix is not
   the selected cohort or a representative random sample. Do not infer global
   counts from its truncated top lists.
3. Explain the observed process, variants, repeated steps, resource changes and
   timestamp limitations. Ground interpretations in source definitions and tool
   results. Propose a coherent simulation scope supported by the records.
4. If Stage 1 is authorized, continue with `generate-environment`. Otherwise,
   answer the investigation request with findings and the next material question.

For BPI 2019, read `data/bpi2019/metadata.json`. Cases are purchase-document
items; categories have different matching rules. Repeated receipts and invoices
can be installments. Do not force all categories into one mandatory flow.

Event gaps include waiting and off-hours. Equal timestamps do not establish
order. Resource IDs do not establish roles, staffing or availability. A long gap
is not proof of a disruption. Historical association is not intervention evidence.

For non-XES input, inspect whether events can be reconstructed and explain the
field mapping and missing evidence. Use existing read-only tools; profiling alone
is not process discovery. Preserve raw data and never invent missing events.
