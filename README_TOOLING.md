# Tooling Module Additions

## Service Needed Report
- **Path:** `/tooling/report/service`
- Lists batches whose latest event sets status to `NEED_SERVICE` with columns for slot, reason, and dimensions.
- Batch links open the tooling card and preserve a smart back navigation to return to the report.

## Service Actions
- New actions `WASH`, `POLISH`, `INSPECT`, and `REPAIR` transition tools to `STOCK` without modifying dimensions.
- Existing `REGRIND` flow remains, still allowing dimension updates.
- Form navigation honours the smart back token so users return to the originating view.

## Auto-remove Enhancements
- Installing into an occupied slot now records an automatic `REMOVE` event with status `NEED_SERVICE`.
- Non `NEW`/`TRIAL` install reasons move to the auto-remove event, ensuring the report surfaces why servicing is required.
