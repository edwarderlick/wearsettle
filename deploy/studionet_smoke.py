"""StudioNet smoke: deploy, fund, move-out, resolve, second resolve.

Run from repo root:
    python deploy/studionet_smoke.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

os.chdir(ROOT)

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded

MOVE_IN = "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg"
MOVE_OUT_404 = (
    "https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg"
)
WALL = 100_000_000_000_000
REMOTE = 50_000_000_000_000
GLASS = 200_000_000_000_000
MAX_TOTAL = WALL + REMOTE + GLASS
INVENTORY_JSON = json.dumps(
    [
        {"id": "wall_scuff", "label": "Wall scuff or hole", "max_charge_wei": WALL},
        {"id": "missing_remote", "label": "TV remote present", "max_charge_wei": REMOTE},
        {
            "id": "broken_glass",
            "label": "Window or glass pane intact",
            "max_charge_wei": GLASS,
        },
    ]
)


def _addr(account) -> str:
    return account.address if hasattr(account, "address") else str(account)


def _txid(receipt) -> str:
    for key in ("id", "hash", "tx_id", "transaction_hash"):
        if hasattr(receipt, key):
            val = getattr(receipt, key)
            if val:
                return str(val)
        if isinstance(receipt, dict) and receipt.get(key):
            return str(receipt[key])
    return str(receipt)


def main() -> None:
    accounts = get_accounts()
    owner, tenant = accounts[0], accounts[1]
    factory = get_contract_factory("WearSettle")
    contract = factory.deploy(
        args=[_addr(tenant), MOVE_IN, 2_592_000, INVENTORY_JSON],
        account=owner,
    )
    print("DEPLOY_ADDRESS", contract.address)

    fund_tx = contract.fund_deposit(args=[]).transact(
        account=tenant,
        value=MAX_TOTAL,
        wait_retries=80,
        wait_interval=2000,
    )
    print("FUND_OK", tx_execution_succeeded(fund_tx), _txid(fund_tx))
    if not tx_execution_succeeded(fund_tx):
        raise SystemExit("fund_deposit failed")

    move_tx = contract.submit_move_out(args=[MOVE_OUT_404]).transact(
        account=tenant,
        wait_retries=80,
        wait_interval=2000,
    )
    print("MOVEOUT_OK", tx_execution_succeeded(move_tx), _txid(move_tx))
    if not tx_execution_succeeded(move_tx):
        raise SystemExit("submit_move_out failed")

    resolve_tx = contract.resolve(args=[]).transact(
        account=owner,
        wait_retries=180,
        wait_interval=3000,
        consensus_max_rotations=6,
    )
    print("RESOLVE_OK", tx_execution_succeeded(resolve_tx), _txid(resolve_tx))
    print("RESOLVE_RECEIPT", resolve_tx)

    case = contract.get_case(args=[]).call()
    settlement = contract.get_settlement(args=[]).call()
    print("CASE", json.dumps(case, default=str))
    print("SETTLEMENT", json.dumps(settlement, default=str))

    second = contract.resolve(args=[]).transact(
        account=owner,
        wait_retries=40,
        wait_interval=2000,
    )
    print(
        "SECOND_RESOLVE_FAILED",
        tx_execution_failed(second) or not tx_execution_succeeded(second),
        _txid(second),
    )

    record = {
        "network": "studionet",
        "chainId": 61999,
        "address": str(contract.address),
        "fund_tx": _txid(fund_tx),
        "moveout_tx": _txid(move_tx),
        "resolve_tx": _txid(resolve_tx),
        "second_resolve_tx": _txid(second),
        "case": case,
        "settlement": settlement,
        "fixture": "C_404_insufficient",
        "move_in": MOVE_IN,
        "move_out": MOVE_OUT_404,
    }
    Path("deploy-result.json").write_text(json.dumps(record, indent=2, default=str))
    print("WROTE deploy-result.json")


if __name__ == "__main__":
    main()
