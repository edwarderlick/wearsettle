# WearSettle

A GenLayer deposit primitive: two public photos in, predetermined inventory out, deterministic wei.

Studio-dev / test GEN only. This is **not** a court, judge, arbitrator, or legal damages award. Validators compare two visual artifacts against a priced inventory and return which **line ids** are chargeable. The contract then pays a sum that cannot drift from those ids.

```
owner_payout  = sum(max_charge_wei[id] for id in triggered)
tenant_refund = deposit_wei - owner_payout
```

The model never emits a wei amount, never emits a percentage, and never invents a payable line.

## What this is not

| Nearby primitive | Why WearSettle is different |
| --- | --- |
| Bounty / deliverable grader | No free-form “was the job done?” score |
| Coverage / challenge market | One occupancy, one `resolve`. No allegation that can freeze the pot |
| Package-version escrow | Inventory is `json.loads` objects, not regex over a blob |
| Numeric split with a tolerance band | Triggered **id set must match exactly**. No average, no “close enough” |
| Frontend LLM that writes a verdict the contract stores | Vision runs **inside** `run_nondet_unsafe`. Validators re-fetch both URLs |

Official GenLayer docs already list “insurance claims with photo proof, damage assessment” under Image Processing. WearSettle is that primitive with a **priced inventory** so money cannot drift from consensus.

## Two-image protocol limit

Live docs (`Calling LLMs` / GenVM config): **maximum two images** per `gl.nondet.exec_prompt`.

v1 evidence is therefore exactly:

- one `move_in_url`
- one `move_out_url`

In the nondet block:

```python
in_img  = gl.nondet.web.render(move_in_url,  mode="screenshot")
out_img = gl.nondet.web.render(move_out_url, mode="screenshot")
result  = gl.nondet.exec_prompt(..., images=[in_img, out_img], response_format="json")
```

**Chosen path: screenshot-of-URL** for both sides (documented Image Processing + Web Access combo). Works for HTML pages and for direct image URLs (the browser paints the image). Do not pass 3+ images. Do not nest `run_nondet_unsafe`.

If a later builder wants multiple angles, they host **one** contact-sheet / collage page and pass that single URL. Inventory stays text, max 8 lines, so two photos can actually be judged.

## State machine

```
AWAITING_DEPOSIT
        │ fund_deposit (value ≥ max_total_charge_wei)
        ▼
     FUNDED ── cancel (owner) ──► CANCELLED (full refund if funded)
        │ expire after move-out deadline, no move-out
        ▼
     EXPIRED (full refund)
        │
        │ submit_move_out (owner only, one shot)
        ▼
MOVEOUT_SUBMITTED
        │ resolve (permissionless)
        │ expire after resolve deadline if resolve never lands
        ▼
     SETTLED  or  EXPIRED (full refund)
        ├── SETTLE + triggered ids → owner lines + depositor rest (marker PAID)
        ├── SETTLE + []           → full depositor refund         (marker PAID)
        └── INSUFFICIENT          → full depositor refund         (marker REFUNDED)
```

One contract = one occupancy. Redeploy for the next tenancy.

## Methods

| Method | Kind | Who | Notes |
| --- | --- | --- | --- |
| `__init__(tenant, move_in_url, move_out_deadline_s, resolve_deadline_s, inventory_json)` | constructor | deployer = owner | **Not payable.** HTTPS URL, 1–8 inventory items. Both deadlines 60–2,592,000 s |
| `fund_deposit()` | write payable | anyone | First fund ≥ `max_total_charge_wei`. Later top-ups do not change `depositor` |
| `submit_move_out(url)` | write | owner | FUNDED, before move-out deadline, one shot. Owner bears proof of damage |
| `cancel()` | write | owner | Before move-out. Refund if funded |
| `expire()` | write | anyone | FUNDED past move-out deadline with no URL, or MOVEOUT_SUBMITTED past resolve deadline. Full depositor refund |
| `resolve()` | write | anyone | MOVEOUT_SUBMITTED, `payout_marker == NONE` |
| `withdraw()` | write | credit holder | Pull if EOA `emit_transfer` failed |
| `get_case()` | view | — | Parties, status, deposit, inventory, marker |
| `get_settlement()` | view | — | **Derived** payout from inventory + triggered + deposit |
| `get_inventory()` | view | — | Structured items |
| `get_credit(addr)` | view | — | Pull balance |

## Economics (terminal states)

| Terminal | Owner | Depositor | Marker |
| --- | --- | --- | --- |
| CANCELLED (never funded) | — | — | NONE |
| CANCELLED (funded) | — | 100% deposit | REFUNDED |
| EXPIRED | — | 100% deposit | REFUNDED |
| SETTLED / INSUFFICIENT | — | 100% deposit | REFUNDED |
| SETTLED / SETTLE, triggered [] | — | 100% deposit | PAID |
| SETTLED / SETTLE, triggered ids | sum of those lines | remainder | PAID |

If `emit_transfer` to an EOA fails on Studio, the same wei is credited on-contract and `withdraw()` pays it. Funds are not trapped.

## Consensus and payout

The prompt lists inventory **ids and labels only**. `max_charge_wei` never enters the model. A photo that says “charge everything” is untrusted data. Only constructor ids are payable names.

- Payout wei is derived from triggered ids + inventory prices + deposit. Nothing stores a separate trusted amount. `get_settlement()` always recomputes.
- Validators re-screenshot both URLs and must match the exact verdict and id set. No tolerance, no average.
- Inventory is `json.loads` of a JSON array; only `id`, `label`, `max_charge_wei`. Extra keys are rejected.
- One occupancy, one resolve. Failed vision refunds the depositor.
- `payout_marker` makes a second resolve revert (`already paid or refunded`).
- Inputs over cap are rejected, not truncated. One settlement blob; no attempt history.
- Triggered ids that are not in the constructor inventory cannot add wei.
- Funded states always exit: cancel, expire (FUNDED or MOVEOUT_SUBMITTED after the matching deadline), insufficient refund, or settle.
- Only the owner may submit move-out evidence (burden of proof for chargeable lines).
- If EOA transfer fails, credit + `withdraw()`.

## Size caps

| Input | Cap |
| --- | --- |
| Inventory items | 1–8 |
| id | 1–32 chars, `^[a-z0-9_]+$` |
| label | 1–120 chars |
| `inventory_json` | 4000 chars |
| URL | 12–256 chars, must start with `https://` |
| Model notes | **not persisted** |
| `move_out_deadline_seconds` | 60–2,592,000 (1 min–30 days) |

Reject oversize inputs. Do not truncate.

## Studio-dev (chain 61997)

Canonical live occupancy matching the updated source (constructor with `resolve_deadline_seconds`, inventory as JSON string, owner-only move-out, and timeout exit paths).

| Field | Value |
| --- | --- |
| Network | Studio-dev |
| RPC | https://studio-dev.genlayer.com/api |
| Chain ID | 61997 |
| Contract | `0x86034B3290a9e3bAC0650B6A1BC5289e8a3E63d6` |
| Deploy tx | `0xbc2099db4bad0468e6b811a1c4697b92d6cc80dca173fedd0bce3414d456775d` |

## StudioNet (chain 61999) - Legacy

Legacy live occupancy (Fixture C — insufficient evidence, full refund). Inspect in Studio: [studio.genlayer.com](https://studio.genlayer.com).

| Field | Value |
| --- | --- |
| Network | StudioNet |
| RPC | https://studio.genlayer.com/api |
| Chain ID | 61999 |
| Explorer | https://explorer-studio.genlayer.com |
| Contract | [0x9420Aed5E9e38d765F2Be41979830e84fBEd1D47](https://explorer-studio.genlayer.com/address/0x9420Aed5E9e38d765F2Be41979830e84fBEd1D47) |
| Resolve tx | [0x0bc8b0d4890161d8f34f676ddf96a584f48fa9788101a96c112d2f1f0f41a972](https://explorer-studio.genlayer.com/tx/0x0bc8b0d4890161d8f34f676ddf96a584f48fa9788101a96c112d2f1f0f41a972) |
| Second resolve tx | [0x84114443167e6c3c9e396a153a1f8d88070f97901a5613b7ef558f9af11b3751](https://explorer-studio.genlayer.com/tx/0x84114443167e6c3c9e396a153a1f8d88070f97901a5613b7ef558f9af11b3751) |
| Consensus | `MAJORITY_AGREE` on first resolve; second resolve **rollback** `already paid or refunded` (5× AGREE, no second transfer) |

`get_case` after resolve:

- `status = SETTLED`
- `payout_marker = REFUNDED`
- `verdict = INSUFFICIENT`
- `triggered_ids = []`
- `owner_payout_wei = 0`
- `tenant_refund_wei = 350000000000000`
- refund message emitted to depositor `0x852272364F9440CAe70b621a04038bB2297350A8`

The occupancy at `0x9420…` was deployed **before** owner-only move-out and the resolve-deadline expire path. This file is the current constructor (`resolve_deadline_seconds`) and those guards. Redeploy to use the new lifecycle. Fixture C on that address remains a historical INSUFFICIENT refund + second-resolve rollback.

Earlier successful constructor deploys (same settlement rules): `0x03339f15e17fD7ceC29139343408fb4cA58d7eE4`, `0x593bB4E9Ac548DB81cAF10B4CeA99f6D6f2d369f` (FUNDED).

A CLI `--args` pass that fed inventory as a JSON **array** instead of a **string** produced tx `0x42be1a01…` / address `0x7D52EfC8…` with `MAJORITY_AGREE` on the **deploy transaction** but **no contract code** (constructor did not stick). Pass `inventory_json` as a string.

## Fixtures (fetched, not invented)

| Fixture | Move-in | Move-out | Live outcome |
| --- | --- | --- | --- |
| A clean | [Hotel room.jpg](https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg) | same URL | Direct-mode SETTLE+[] covered. Live A not re-run after Studio 502s; same URLs |
| B chargeable | Hotel room.jpg | [Broken glass.jpg](https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg) | **Not claimed live.** Studio vision may return INSUFFICIENT on lighting / unrelated object. Money rules still exact-id |
| C insufficient | Hotel room.jpg | [404 JPEG](https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg) | **Live:** INSUFFICIENT, full refund, second resolve cannot pay |

## Two-step deploy

Constructors are not payable. Deploy, then `fund_deposit` with `value >= max_total_charge_wei`.

```bash
genvm-lint check contracts/wearsettle.py
pytest test/test_wearsettle_direct.py -v
gltest test/test_wearsettle_integration.py::test_fixture_c_insufficient_404 -v -s --network studionet

genlayer network set studionet
genlayer deploy --contract contracts/wearsettle.py --args <tenant> "<https-move-in>" 2592000 2592000 "<inventory json STRING>"
# then payable fund_deposit via genlayer-js / gltest (CLI write currently sends value=0)
```

`deploy/001_deploy_wearsettle.ts` is the fee-aware-style script for `genlayer deploy` (constructor + optional fund/move-out/resolve). StudioNet is gasless.

## Forking

Redeploy per occupancy. Swap the inventory for venue hire, an equipment locker, or a costume deposit. Keep **one URL per side**. For extra angles, publish a contact sheet. Do not add a gallery, a challenge path, or an LLM-proposed wei amount.

## Tests

```bash
# Direct guards: constructor, undersized fund, one-shot owner move-out,
# cancel/expire exits, double resolve, derived payout, invented id, size caps
pytest test/test_wearsettle_direct.py -v

# Live StudioNet (slow, real vision)
gltest test/test_wearsettle_integration.py -v -s --network studionet
```

Direct mode on this Windows box: **30 passed**. `genlayer-test` screenshot mocks return empty PNG bytes; tests patch `wasi_mock._handle_web_render` with a real 2×2 PNG so PIL can open the artifact. If `os.unlink` on an open handle appears in a future runner, treat Studio integration + lint as the network proof and keep these money assertions.

## Known limitations

- Test GEN on StudioNet only. No legal enforceability.
- Public HTTPS artifacts only. Validators must be able to render them.
- Hard 2-image cap.
- Studio IC→EOA may fall back to `credits` + `withdraw()`.
- Vision models can return `INSUFFICIENT` on bad lighting, 404 pages, or unrelated photos. That is a **full refund**, not a freeze.
- `genlayer write` (CLI 0.39.2) hardcodes `value: 0n`. Payable `fund_deposit` needs genlayer-js / gltest `transact(value=…)`.
- Nondet closures must not pickle storage; `resolve` copies ids/labels/URLs into locals first.

## License

Source as-is for StudioNet / test GEN. Not a legal instrument.
