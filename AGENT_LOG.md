# WearSettle — AGENT_LOG

Living decision log. Updated after research, API choices, lint, tests, and deploy.

## 2026-09-06 — Start

- Workspace `D:\WearSettle` was empty (no prior source). This is a WearSettle-only contract repo. No frontend. No git push.
- Skills in use: write-contract / genvm-lint / direct-tests / integration-tests / genlayer-cli; agent-reach (Jina Reader + GitHub search) for live docs; Wikimedia API for fixture URL confirmation.
- Local tooling: Python 3.12.10, genlayer-test 0.29.2, genvm-linter 0.11.0, genlayer CLI 0.39.2. Active CLI network is StudioNet (`chainId` 61999, `https://studio.genlayer.com/api`). Active account `coverlock-submitter` `0x9ce8b4b8a355421f01779ebd0c49e22a8f1ff0dd` unlocked with test GEN.

## Step 0 — Live API confirmation (not memory)

Sources (fetched via agent-reach Jina Reader + docs.genlayer.com search):

| Topic | Live source | Decision |
| --- | --- | --- |
| Image limit | [Calling LLMs](https://docs.genlayer.com/developers/intelligent-contracts/features/calling-llms) — “Limit of images is two”; GenVM config: “text + up to 2 images” | v1 evidence is exactly two URLs → two screenshots → one `exec_prompt` |
| Image + web | [Image Processing](https://docs.genlayer.com/developers/intelligent-contracts/features/image-processing) — `gl.nondet.web.render(url, mode='screenshot')` then `exec_prompt(..., images=[...])`. `images` accepts raw `bytes` or `gl.nondet.Image` | **Chosen path: screenshot-of-URL for both sides.** Works for HTML pages and direct image URLs (browser paints the image). Avoids content-type branching on `web.get` bytes. Product rule: exactly two visual artifacts enter the prompt. |
| Nested nondet | write-contract skill + GenVM: one `run_nondet_unsafe`; leader may call web+llm sequentially | No nested `run_nondet_unsafe`. No 3+ images. No gallery. |
| Payable constructor | Value Transfers docs: value only on `@gl.public.write.payable`. `__init__` is not a public write method. Studio deploy is constructor params then deploy, no value field on init. | Two-step: constructor → `fund_deposit()`. |
| Value in | `@gl.public.write.payable` + `gl.message.value` (`u256`) | `fund_deposit` only. `__receive__` reverts so stray transfers cannot bypass coverage checks. |
| Value out to EOA | `_Recipient(addr).emit_transfer(value=v)` via `@gl.evm.contract_interface`. Studio: EVM beyond EOA transfers is limited; IC→EOA can fail. | Try emit; on exception or explicit `False`, credit `credits[addr]` and expose `withdraw()`. |
| Time | [Transaction Context](https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context) — `datetime.now(timezone.utc)` is the **transaction** timestamp | `deploy_ts` and deadline arithmetic use that clock. Direct tests use `direct_vm.warp(ISO)`. |
| Equivalence | `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`. Validator must re-render and re-prompt. | Accept only exact `verdict` + sanitized `triggered` set. No tolerance (FairSplit). No notes comparison. |
| Runner pin | write-contract skill (current) | `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }` |
| StudioNet | [Networks](https://docs.genlayer.com/developers/networks) | RPC `https://studio.genlayer.com/api`, chain 61999, gasless deploy, built-in faucet. |
| Deploy scripts | [Deploy Scripts](https://docs.genlayer.com/developers/intelligent-contracts/deploying/deploy-scripts) | `deploy/001_deploy_wearsettle.ts` for `genlayer deploy`. StudioNet: no fee profile required. |
| Prompt injection | [Prompt injection](https://docs.genlayer.com/developers/intelligent-contracts/security-and-best-practices/prompt-injection) | Prompt treats visual contents as untrusted. Only constructor inventory ids are payable. |

## Prior-art check

Searched GitHub (`gh search code/repos`) and GenLayer docs/examples:

- No repository named WearSettle.
- No Python contract using `move_in_url` + priced inventory `max_charge_wei`.
- Nearby but **not** this primitive: bounty/intent settlement, parametric flight insurance, content moderator, prediction markets, generic escrow. Official image-processing docs list “insurance claims with photo proof, damage assessment” as a use case — that is the category, not a shipped deposit+two-image+predetermined-line contract.

**Conclusion:** no exact prior art. Proceeding to implement.

## Product rules locked

- One occupancy per deployment.
- Money source of truth: `(triggered_ids, inventory prices, deposit_wei)` recomputed before every transfer and in `get_settlement()`.
- Validators: exact triggered-id set + exact verdict. Disagreement → `validator_fn` returns False (rotation).
- Inventory parsed with `json.loads` into objects; only top-level `id`, `label`, `max_charge_wei`. Extra keys rejected (VersionLock).
- No challenge market (CoverLock). Failed vision → `INSUFFICIENT` + full depositor refund. Status `SETTLED`, marker `REFUNDED`.
- `payout_marker` in `{NONE, PAID, REFUNDED}`. `PENDING` is named in the spec set but never persisted: a successful `resolve` transaction either completes to PAID/REFUNDED or reverts entirely. Second `resolve` reverts (PatchLock).
- Every funded state has an exit: cancel / expire / INSUFFICIENT refund / SETTLE split.
- Invalid ids dropped; they cannot pay (ProofReader).
- Size caps as specified (Ironclad).
- `INSUFFICIENT` is not a separate status. Both clean SETTLE and INSUFFICIENT end in `SETTLED`; distinguish via `verdict` + marker + triggered set.

## Fixture URLs (fetched, not invented)

Confirmed 200:

- Move-in / clean move-out: `https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg` (Wikimedia `File:Hotel room.jpg`)
- Chargeable move-out: `https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg` (Wikimedia `File:Broken glass.jpg`)
- Alternate chargeable: `https://upload.wikimedia.org/wikipedia/commons/5/5d/Broken_window.jpg`

Confirmed 404:

- `https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg`

Also confirmed 200 (not used as occupancy fixtures): Commons `Cat03.jpg`, PNG transparency demo.

## Implementation notes (as built)

- Screenshot path used in `resolve()` leader and validator.
- Prices omitted from the vision prompt.
- Notes from the model are discarded (not stored).
- `get_settlement()` never reads a stored payout field.

## Lint / tests / deploy

### Contract

- Removed `__receive__`: this genvm-linter (0.11.0) rejects public names starting with `__` even when docs require `@gl.public.write.payable` on `__receive__`. Stray value-only transfers are unused; `fund_deposit` is the only payable path.
- Constructor `tenant` wrapped with `Address(...)` because direct-mode calldata roundtrip delivers `bytes`.
- `resolve` checks `payout_marker` **before** status so a SETTLED occupancy returns `already paid or refunded` (PatchLock), not `resolve requires MOVEOUT_SUBMITTED`.
- Vision helper is a module-level `_run_vision(allowed, labels, move_in, move_out)` so the nondet closure does not pickle storage. Live Fixture C still warned `Detected pickling storage class` on the **pre-refactor** bytecode and succeeded anyway.

### Direct tests

- First failure: `bytes` has no `as_bytes` on `self.tenant = tenant`. Fixed with `_as_address`.
- Screenshot mocks in genlayer-test return `image: b""`; PIL in `web.render` then throws; our `except` mapped that to INSUFFICIENT and hid SETTLE paths. Tests now patch `wasi_mock._handle_web_render` with a real 2×2 PNG.
- **28 passed** on Windows (`pytest test/test_wearsettle_direct.py`). No `os.unlink` failure this run.

### StudioNet

- gltest `factory.deploy` often deploys then fails `get_contract_schema_for_code` (all clients). Fallback: `deploy_contract_tx` + `genvm-lint schema --json` + `Contract.new`.
- `ContractFunction.transact()` does **not** take `account=`; bind via `Contract.new(..., account=funder)`.
- Studio 502 / Cloudflare HTML during `eth_getTransactionByHash` after fund. On-chain, fund still landed on `0x593bB4E9Ac548DB81cAF10B4CeA99f6D6f2d369f`.
- CLI `genlayer write` hardcodes `value: 0n` — cannot `fund_deposit` from CLI 0.39.2. gltest `transact(value=…)` works.
- CLI `--args` JSON array is parsed as an array, not a string. Tx `0x42be1a01…` / `0x7D52EfC8…` was `MAJORITY_AGREE` on the deploy tx but **no contract code** (constructor did not stick). Pass inventory as a string.
- **Live Fixture C** `0x9420Aed5E9e38d765F2Be41979830e84fBEd1D47`
  - resolve `0x0bc8b0d4…` SUCCESS, leader `{"triggered":[],"verdict":"INSUFFICIENT"}`, MAJORITY_AGREE, refund message `350000000000000` to depositor
  - second resolve `0x84114443…` rollback payload `already paid or refunded`, no second transfer
- Fixture B chargeable line **not claimed live** (Studio 502 budget + vision may INSUFFICIENT on hotel-room vs broken-glass). Direct tests cover exact-id money.

### API choice (screenshot vs raw bytes)

**Screenshot-of-URL** (`gl.nondet.web.render(..., mode='screenshot')`) for both artifacts. Confirmed on live Studio: 404 move-out produced INSUFFICIENT as designed. Raw `web.get` bytes not used.

### Prior art

No deposit + two-image + predetermined priced inventory contract found. Proceeded.

### Not done (pre-audit)

- No git push, no GitHub remote (until steward audit push gate).
- No frontend.
- Fixture A/B live vision not re-run after C succeeded; C + direct money tests satisfy “at least one live resolve” + PatchLock on-chain.

## STEWARD AUDIT (2026-09-06)

Read: `contracts/wearsettle.py` (full), both test files, README, AGENTS, deploy scripts, gltest config, requirements, `.gitignore`. Live `get_case` / `get_settlement` / `genlayer code` on `0x9420Aed5E9e38d765F2Be41979830e84fBEd1D47`. Compared Ironclad README via GitHub API (bounty / `attempt_break` / judge LLM) — not this primitive; WearSettle source is not a copy.

### A–L

| ID | Finding | Verdict | Guard (quote) |
| --- | --- | --- | --- |
| A | Concord stored vs recomputed | **PASS** | No stored payout wei. `get_settlement` calls `_recompute_payout()` from `triggered_ids` + `inventory_charges` + `deposit_wei`. `resolve` SETTLE path: `if owner_payout != recomputed: raise ... "payout does not match inventory sum"`. LLM JSON never written as wei. |
| B | FairSplit tolerance / leader-only | **PASS** | `validator_fn`: `leader_san = _sanitize_vision(leaders_res.calldata, allowed)` then `validator_san = leader_fn()` (`_run_vision` re-screenshots both URLs and re-prompts). True only if `verdict` and `triggered` lists equal. No tolerance/average. |
| C | VersionLock regex | **PASS** | `_parse_inventory` uses `json.loads` into a list of objects; extra keys rejected; `ID_RE` is charset on the parsed `id` field only, never scans the blob for amounts. Nested `version` bait rejected. |
| D | CoverLock freeze | **PASS** | No challenge object. INSUFFICIENT → refund + `SETTLED`/`REFUNDED`. `cancel` on AWAITING/FUNDED. `expire` on FUNDED after deadline. |
| E | PatchLock double pay | **PASS** (test **FIXED** this audit) | `if self.payout_marker != MARKER_NONE: raise ... "already paid or refunded"` before vision. Marker set before `_pay`. Direct test now also asserts settlement wei unchanged after the second call. Live second resolve `0x84114443…` rollback `already paid or refunded`. |
| F | Ironclad caps | **PASS** | 1–8 items, id/label/url/json lengths, HTTPS, reject not truncate, no attempt history. |
| G | ProofReader invented id | **PASS** | `_sanitize_vision` drops ids not in `allowed`; INSUFFICIENT forces `triggered=[]`. Direct: `item_99` cannot add wei. |
| H | Concord bond freeze | **PASS** | Unfunded cancel; funded expire; junk URL → INSUFFICIENT refund; MOVEOUT_SUBMITTED has permissionless `resolve`. |
| I | emit_transfer fail | **PASS** | `_Recipient.emit_transfer`; `False`/exception → `credits[to] += amount`; `withdraw()` zeros then emits, restores credit on fail. |
| J | Two-image cap | **PASS** | One `exec_prompt(..., images=[in_img, out_img])`. No nested `run_nondet_unsafe`. |
| K | Constructor not payable | **PASS** | `__init__` never reads `gl.message.value`. Value only in `fund_deposit`. |
| L | Not a clone / not a court | **PASS** | README frames as deposit primitive and **not** a court. No bounty `attempt_break`. No imports from other account projects. Prompt disclaimer uses “not a court” as a negative, not a claim. |

### Chain vs repo

- Live `0x9420…` still `SETTLED` / `REFUNDED` / `INSUFFICIENT` / `triggered []` / refund 350e12. Matches Fixture C.
- Live code still has `_vision_task(self)`. Repo has `_run_vision(...)` (no storage pickle). **Not a money-logic change.** Documented in README. No replacement deploy.

### Other audit nits

- `.gitignore`: added `.env.*` and `*.compiled.js` (**FIXED**).
- No `.env` / private keys in tree.
- README methods/economics match code. Fixture B remains not claimed live.
- Clone check vs Ironclad: different product (bounty vs deposit inventory).

### Tests this audit

`genvm-lint check contracts/wearsettle.py` + `pytest test/test_wearsettle_direct.py -v` after PatchLock assertion tighten.
