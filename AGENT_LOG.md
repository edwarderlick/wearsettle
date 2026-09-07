# WearSettle — build log

StudioNet / test GEN. Deposit primitive: two public photos in, priced inventory out, deterministic wei.

## APIs used (live docs)

- Image cap: two images per `gl.nondet.exec_prompt` ([Calling LLMs](https://docs.genlayer.com/developers/intelligent-contracts/features/calling-llms)).
- Vision + web: `gl.nondet.web.render(url, mode="screenshot")` then `exec_prompt(..., images=[in_img, out_img], response_format="json")` ([Image Processing](https://docs.genlayer.com/developers/intelligent-contracts/features/image-processing), [Web Access](https://docs.genlayer.com/developers/intelligent-contracts/features/web-access)).
- Consensus: `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`. Validator re-renders both URLs and re-runs the same prompt. Accept only exact `verdict` + sanitized triggered id set.
- Value in: `@gl.public.write.payable` + `gl.message.value` on `fund_deposit` only. Constructor is not payable ([Value Transfers](https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers)).
- Value out: `_Recipient(addr).emit_transfer(value=v)`. On failure, `credits[addr]` + `withdraw()`.
- Time: transaction clock via `datetime.now(timezone.utc)` ([Transaction Context](https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context)).
- Runner pin: `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`.
- StudioNet: RPC `https://studio.genlayer.com/api`, chain **61999**, explorer `https://explorer-studio.genlayer.com` ([Networks](https://docs.genlayer.com/developers/networks)).

## Fixture URLs (fetched)

- Move-in / clean: `https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg` (HTTP 200).
- Chargeable move-out: `https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg` (HTTP 200). Not claimed as a live vision pass.
- Insufficient: `https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg` (HTTP 404).

## Lint / tests

- `genvm-lint check contracts/wearsettle.py` — clean (10 methods: 4 view, 6 write).
- `pytest test/test_wearsettle_direct.py -v` — 30 passed on Windows after owner-only move-out + resolve-deadline expire. Screenshot mocks in genlayer-test return empty PNG bytes; tests patch `wasi_mock._handle_web_render` with a real 2×2 PNG.

## StudioNet occupancy (Fixture C)

- Contract: `0x9420Aed5E9e38d765F2Be41979830e84fBEd1D47`
- Resolve: `0x0bc8b0d4890161d8f34f676ddf96a584f48fa9788101a96c112d2f1f0f41a972` — `INSUFFICIENT`, `SETTLED`, `REFUNDED`, full depositor refund `350000000000000`.
- Second resolve: `0x84114443167e6c3c9e396a153a1f8d88070f97901a5613b7ef558f9af11b3751` — rollback `already paid or refunded`, no second transfer.

`0x9420…` predates owner-only `submit_move_out` and `expire` from `MOVEOUT_SUBMITTED` (resolve deadline). Current constructor takes `resolve_deadline_seconds`; `expire` refunds if resolve never lands. Redeploy to use that lifecycle.

CLI notes: `genlayer write` (0.39.2) hardcodes `value: 0n`; payable `fund_deposit` needs genlayer-js / gltest `transact(value=…)`. Pass `inventory_json` as a string, not a parsed JSON array.
