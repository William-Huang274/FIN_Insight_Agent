# R18 Vertical Source-Route Gate

- Generated at: `2026-06-23T19:48:27Z`
- Status: `action_required`
- Companies: `603`
- Pass companies: `600`
- Action-required companies: `3`
- Requirements: `5177`
- Passed requirements: `5174`
- Missing requirements: `3`

## Missing Source Roles

- `public_order_proxy`: `3`

## Root Causes

- `source_or_adapter_gap`: `2`
- `route_or_parser_debt`: `1`

## Lane Status

- `V1`: pass `41`, action_required `2`
- `V2`: pass `9`, action_required `0`
- `V3`: pass `96`, action_required `0`
- `V4`: pass `68`, action_required `0`
- `V5`: pass `14`, action_required `0`
- `V6`: pass `77`, action_required `0`
- `V7`: pass `214`, action_required `1`
- `V8`: pass `81`, action_required `0`

## Action Required Companies

- `2382.TW` `V1`: public_order_proxy
- `CRDO` `V1`: public_order_proxy
- `DNN` `V7`: public_order_proxy

## Boundary

- This is a diagnostic gate over required source roles. It does not mean every product/SKU/KPI is complete.
- Missing requirements are not hidden as fallback evidence; they remain source-route, parser, resolver, or public-boundary work.
