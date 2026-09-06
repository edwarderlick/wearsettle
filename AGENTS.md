# WearSettle — agent runbook

This folder is **WearSettle only**. Do not build a frontend.

## What it is

A GenLayer deposit primitive: two public photos in, predetermined inventory out, deterministic wei. StudioNet / test GEN. Not a court.

## Layout

- `contracts/wearsettle.py` — Intelligent Contract (pinned `py-genlayer` runner)
- `test/test_wearsettle_direct.py` — in-memory guards
- `test/test_wearsettle_integration.py` — StudioNet live consensus
- `deploy/001_deploy_wearsettle.ts` — `genlayer deploy`
- `AGENT_LOG.md` — APIs, fixture URLs, lint/test counts, StudioNet txs

## Commands

```bash
genvm-lint check contracts/wearsettle.py
pytest test/test_wearsettle_direct.py -v
gltest test/test_wearsettle_integration.py -v -s --network studionet
genlayer network set studionet
genlayer deploy --contract contracts/wearsettle.py --args "<tenant>" "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg" 2592000 "<inventory_json>"
```

Constructor is **not** payable. After deploy, call `fund_deposit` with `value >= max_total_charge_wei`.

## Consensus rule

Validators re-screenshot both URLs and re-run the same vision prompt. Accept only if sanitized `verdict` and `triggered` id set are **exactly equal**. No tolerance.

## Money rule

`owner_payout = sum(max_charge_wei[id] for id in triggered_ids)` then `tenant_refund = deposit - owner_payout`. `get_settlement()` always recomputes. Invalid ids never pay.

## Evidence cap

`exec_prompt` accepts at most two images. Forkers who want more angles host a contact sheet as one URL.
