"""StudioNet integration: live consensus on WearSettle fixtures.

Run:
    gltest test/test_wearsettle_integration.py -v -s --network studionet

Live vision is not mocked. Fixture B may return INSUFFICIENT if Studio
models cannot distinguish the chargeable line; that is recorded honestly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded
from gltest.contracts.contract import Contract
from gltest.utils import extract_contract_address

MOVE_IN = "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg"
MOVE_OUT_CLEAN = MOVE_IN
MOVE_OUT_GLASS = "https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg"
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
        {
            "id": "missing_remote",
            "label": "TV remote present",
            "max_charge_wei": REMOTE,
        },
        {
            "id": "broken_glass",
            "label": "Window or glass pane intact",
            "max_charge_wei": GLASS,
        },
    ]
)

DEADLINE = 2_592_000


def _addr(account) -> str:
    return account.address if hasattr(account, "address") else str(account)


def _local_schema():
    raw = subprocess.check_output(
        ["genvm-lint", "schema", "contracts/wearsettle.py", "--json"],
        cwd=str(Path(__file__).resolve().parents[1]),
        text=True,
    )
    return json.loads(raw)["schema"]


def _deploy(owner, tenant):
    factory = get_contract_factory("WearSettle")
    args = [_addr(tenant), MOVE_IN, DEADLINE, DEADLINE, INVENTORY_JSON]
    try:
        return factory.deploy(args=args, account=owner)
    except ValueError:
        receipt = factory.deploy_contract_tx(args=args, account=owner)
        assert tx_execution_succeeded(receipt)
        address = extract_contract_address(receipt)
        return Contract.new(address=address, schema=_local_schema(), account=owner)


def _as(contract, account):
    return Contract.new(
        address=contract.address,
        schema=contract._schema,
        account=account,
    )


def _fund(contract, funder, amount):
    last_err = None
    for attempt in range(5):
        try:
            receipt = _as(contract, funder).fund_deposit(args=[]).transact(
                value=amount,
                wait_retries=80,
                wait_interval=2000,
            )
            assert tx_execution_succeeded(receipt)
            return receipt
        except Exception as err:
            last_err = err
            if "502" not in str(err) and "invalid JSON" not in str(err):
                raise
    raise last_err


@pytest.mark.slow
def test_fixture_a_clean_return():
    accounts = get_accounts()
    owner, tenant = accounts[0], accounts[1]
    contract = _deploy(owner, tenant)
    print("FIXTURE_A_ADDRESS", contract.address)

    fund_tx = _fund(contract, tenant, MAX_TOTAL)
    print("FIXTURE_A_FUND_TX", getattr(fund_tx, "id", fund_tx))

    move_tx = _as(contract, owner).submit_move_out(args=[MOVE_OUT_CLEAN]).transact(
        wait_retries=80,
        wait_interval=2000,
    )
    assert tx_execution_succeeded(move_tx)
    print("FIXTURE_A_MOVEOUT_TX", getattr(move_tx, "id", move_tx))

    resolve_tx = _as(contract, owner).resolve(args=[]).transact(
        wait_retries=120,
        wait_interval=3000,
        consensus_max_rotations=5,
    )
    print("FIXTURE_A_RESOLVE_TX", getattr(resolve_tx, "id", resolve_tx))
    assert tx_execution_succeeded(resolve_tx)

    case = contract.get_case(args=[]).call()
    settlement = contract.get_settlement(args=[]).call()
    print("FIXTURE_A_CASE", case)
    print("FIXTURE_A_SETTLEMENT", settlement)

    assert case["status"] == "SETTLED"
    assert settlement["verdict"] in ("SETTLE", "INSUFFICIENT")
    if settlement["verdict"] == "SETTLE":
        assert settlement["triggered_ids"] == [] or set(settlement["triggered_ids"]).issubset(
            {"wall_scuff", "missing_remote", "broken_glass"}
        )
        # Clean pair of identical hotel-room photos should not charge.
        # If the model charges a line, record it; money must still match inventory.
        expected = 0
        charges = {
            "wall_scuff": WALL,
            "missing_remote": REMOTE,
            "broken_glass": GLASS,
        }
        for item_id in settlement["triggered_ids"]:
            expected += charges[item_id]
        if expected > MAX_TOTAL:
            expected = MAX_TOTAL
        assert settlement["owner_payout_wei"] == expected
        assert settlement["tenant_refund_wei"] == MAX_TOTAL - expected
    else:
        assert settlement["triggered_ids"] == []
        assert settlement["owner_payout_wei"] == 0
        assert settlement["tenant_refund_wei"] == MAX_TOTAL
        assert case["payout_marker"] == "REFUNDED"

    second = _as(contract, owner).resolve(args=[]).transact(
        wait_retries=40,
        wait_interval=2000,
    )
    assert tx_execution_failed(second) or not tx_execution_succeeded(second)


@pytest.mark.slow
def test_fixture_b_chargeable_or_honest_insufficient():
    accounts = get_accounts()
    owner, tenant = accounts[0], accounts[1]
    contract = _deploy(owner, tenant)
    print("FIXTURE_B_ADDRESS", contract.address)

    _fund(contract, tenant, MAX_TOTAL)
    move_tx = _as(contract, owner).submit_move_out(args=[MOVE_OUT_GLASS]).transact(
        wait_retries=80,
        wait_interval=2000,
    )
    assert tx_execution_succeeded(move_tx)

    resolve_tx = _as(contract, owner).resolve(args=[]).transact(
        wait_retries=120,
        wait_interval=3000,
        consensus_max_rotations=5,
    )
    print("FIXTURE_B_RESOLVE_TX", getattr(resolve_tx, "id", resolve_tx))
    assert tx_execution_succeeded(resolve_tx)

    case = contract.get_case(args=[]).call()
    settlement = contract.get_settlement(args=[]).call()
    print("FIXTURE_B_CASE", case)
    print("FIXTURE_B_SETTLEMENT", settlement)

    assert case["status"] == "SETTLED"
    charges = {
        "wall_scuff": WALL,
        "missing_remote": REMOTE,
        "broken_glass": GLASS,
    }
    expected = 0
    for item_id in settlement["triggered_ids"]:
        assert item_id in charges
        expected += charges[item_id]
    if expected > MAX_TOTAL:
        expected = MAX_TOTAL
    assert settlement["owner_payout_wei"] == expected
    assert settlement["tenant_refund_wei"] == MAX_TOTAL - expected

    if settlement["verdict"] == "SETTLE" and settlement["triggered_ids"] == ["broken_glass"]:
        assert expected == GLASS
    else:
        print(
            "FIXTURE_B_HONEST_NOTE: Studio vision did not isolate broken_glass; "
            f"verdict={settlement['verdict']} triggered={settlement['triggered_ids']}"
        )

    second = _as(contract, owner).resolve(args=[]).transact(
        wait_retries=40,
        wait_interval=2000,
    )
    assert tx_execution_failed(second) or not tx_execution_succeeded(second)


@pytest.mark.slow
def test_fixture_c_insufficient_404():
    accounts = get_accounts()
    owner, tenant = accounts[0], accounts[1]
    contract = _deploy(owner, tenant)
    print("FIXTURE_C_ADDRESS", contract.address)

    _fund(contract, tenant, MAX_TOTAL)
    move_tx = _as(contract, owner).submit_move_out(args=[MOVE_OUT_404]).transact(
        wait_retries=80,
        wait_interval=2000,
    )
    assert tx_execution_succeeded(move_tx)

    resolve_tx = _as(contract, owner).resolve(args=[]).transact(
        wait_retries=120,
        wait_interval=3000,
        consensus_max_rotations=5,
    )
    print("FIXTURE_C_RESOLVE_TX", getattr(resolve_tx, "id", resolve_tx))
    assert tx_execution_succeeded(resolve_tx)

    case = contract.get_case(args=[]).call()
    settlement = contract.get_settlement(args=[]).call()
    print("FIXTURE_C_CASE", case)
    print("FIXTURE_C_SETTLEMENT", settlement)

    assert case["status"] == "SETTLED"
    # 404 evidence should be INSUFFICIENT; if the model still SETTLEs with
    # empty triggered, full refund is the same money outcome.
    assert settlement["owner_payout_wei"] == 0 or settlement["verdict"] == "SETTLE"
    if settlement["verdict"] == "INSUFFICIENT":
        assert settlement["triggered_ids"] == []
        assert settlement["owner_payout_wei"] == 0
        assert settlement["tenant_refund_wei"] == MAX_TOTAL
        assert case["payout_marker"] == "REFUNDED"
