"""Direct-mode guards for WearSettle. No live vision required."""

from __future__ import annotations

import io
import json

from PIL import Image as PILImage

import gltest.direct.wasi_mock as wasi_mock

CONTRACT = "contracts/wearsettle.py"

MOVE_IN = "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg"
MOVE_OUT = "https://upload.wikimedia.org/wikipedia/commons/6/67/Broken_glass.jpg"
HTTPS_OK = "https://example.com/a"

WALL = 100_000_000_000_000
REMOTE = 50_000_000_000_000
GLASS = 200_000_000_000_000
MAX_TOTAL = WALL + REMOTE + GLASS

INVENTORY = [
    {"id": "wall_scuff", "label": "Wall scuff or hole", "max_charge_wei": WALL},
    {"id": "missing_remote", "label": "TV remote present", "max_charge_wei": REMOTE},
    {"id": "broken_glass", "label": "Window or glass pane intact", "max_charge_wei": GLASS},
]


def _inv(items=None) -> str:
    return json.dumps(items if items is not None else INVENTORY)


def _hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return str(addr.as_hex).lower()
    if isinstance(addr, (bytes, bytearray)):
        return "0x" + bytes(addr).hex()
    s = str(addr).lower()
    if s.startswith("0x"):
        return s
    return s


def _minimal_png() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (2, 2), (20, 20, 20)).save(buf, format="PNG")
    return buf.getvalue()


_PNG = _minimal_png()
_ORIG_WEB_RENDER = wasi_mock._handle_web_render


def _png_web_render(vm, data):
    mode = data.get("mode", "text")
    if mode == "screenshot":
        return {"ok": {"image": _PNG}}
    return _ORIG_WEB_RENDER(vm, data)


def _deploy(
    direct_vm,
    direct_deploy,
    owner,
    tenant,
    url=MOVE_IN,
    deadline=3600,
    inventory=None,
):
    direct_vm.sender = owner
    return direct_deploy(CONTRACT, tenant, url, deadline, _inv(inventory))


def _fund(direct_vm, contract, funder, amount):
    direct_vm.sender = funder
    direct_vm.value = amount
    contract.fund_deposit()
    direct_vm.value = 0


def _mock_vision(direct_vm, payload: dict):
    wasi_mock._handle_web_render = _png_web_render
    direct_vm.mock_web(r".*", {"status": 200, "body": _PNG})
    direct_vm.mock_llm(r".*", json.dumps(payload))


def test_constructor_rejects_owner_equals_tenant(
    direct_vm, direct_deploy, direct_alice
):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("tenant cannot equal owner"):
        direct_deploy(CONTRACT, direct_alice, MOVE_IN, 3600, _inv())


def test_constructor_rejects_empty_inventory(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("inventory must contain 1 to 8 items"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, "[]")


def test_constructor_rejects_nine_items(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    items = [
        {"id": f"item_{i}", "label": f"Label {i}", "max_charge_wei": 1}
        for i in range(9)
    ]
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("inventory must contain 1 to 8 items"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, _inv(items))


def test_constructor_rejects_duplicate_ids(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    items = [
        {"id": "wall_scuff", "label": "A", "max_charge_wei": 1},
        {"id": "wall_scuff", "label": "B", "max_charge_wei": 1},
    ]
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("duplicate inventory id"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, _inv(items))


def test_constructor_rejects_non_https(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("move_in_url must be https"):
        direct_deploy(CONTRACT, direct_bob, "http://example.com/x", 3600, _inv())


def test_constructor_rejects_non_json(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("inventory_json is not valid JSON"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, "not-json")


def test_constructor_rejects_nested_version_bait(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    items = [
        {
            "id": "wall_scuff",
            "label": "Wall",
            "max_charge_wei": 1,
            "version": {"dependencies": {"foo": "1.2.3"}},
        }
    ]
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("extra money-bearing or nested bait keys"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, _inv(items))


def test_constructor_rejects_missing_max_charge(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    items = [{"id": "wall_scuff", "label": "Wall"}]
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("missing id, label, or max_charge_wei"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, json.dumps(items))


def test_constructor_rejects_empty_label(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    items = [{"id": "wall_scuff", "label": "", "max_charge_wei": 1}]
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("inventory label length invalid"):
        direct_deploy(CONTRACT, direct_bob, MOVE_IN, 3600, _inv(items))


def test_constructor_rejects_257_char_url(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    url = "https://" + ("a" * 249)
    assert len(url) == 257
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("move_in_url must be https"):
        direct_deploy(CONTRACT, direct_bob, url, 3600, _inv())


def test_fund_undersized_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("first fund must cover max_total_charge_wei"):
        _fund(direct_vm, c, direct_bob, MAX_TOTAL - 1)


def test_fund_exact_sets_funded_and_depositor(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    case = c.get_case()
    assert case["status"] == "FUNDED"
    assert case["deposit_wei"] == MAX_TOTAL
    assert case["depositor"].lower() == _hex(direct_bob)
    assert case["max_total_charge_wei"] == MAX_TOTAL


def test_top_up_does_not_change_depositor(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    _fund(direct_vm, c, direct_charlie, 1)
    case = c.get_case()
    assert case["deposit_wei"] == MAX_TOTAL + 1
    assert case["depositor"].lower() == _hex(direct_bob)


def test_submit_move_out_stranger_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only owner or tenant"):
        c.submit_move_out(MOVE_OUT)


def test_submit_move_out_once_from_tenant(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    assert c.get_case()["status"] == "MOVEOUT_SUBMITTED"
    with direct_vm.expect_revert("move-out already submitted"):
        c.submit_move_out(HTTPS_OK)


def test_cancel_after_move_out_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("cannot cancel"):
        c.cancel()


def test_cancel_while_funded_refunds(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_alice
    c.cancel()
    case = c.get_case()
    assert case["status"] == "CANCELLED"
    assert case["payout_marker"] == "REFUNDED"
    credit = c.get_credit(direct_bob)
    # Either native transfer succeeded (credit 0) or fallback credit was booked.
    assert credit in (0, MAX_TOTAL)


def test_expire_before_deadline_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    direct_vm.warp("2026-01-01T00:00:00+00:00")
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob, deadline=120)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.warp("2026-01-01T00:01:00+00:00")
    with direct_vm.expect_revert("deadline not reached"):
        c.expire()


def test_expire_after_deadline_refunds(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    direct_vm.warp("2026-01-01T00:00:00+00:00")
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob, deadline=60)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.warp("2026-01-01T00:02:00+00:00")
    c.expire()
    case = c.get_case()
    assert case["status"] == "EXPIRED"
    assert case["payout_marker"] == "REFUNDED"


def test_resolve_before_move_out_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    with direct_vm.expect_revert("resolve requires MOVEOUT_SUBMITTED"):
        c.resolve()


def test_second_resolve_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    _mock_vision(direct_vm, {"verdict": "SETTLE", "triggered": ["broken_glass"]})
    c.resolve()
    case = c.get_case()
    settlement = c.get_settlement()
    assert case["status"] == "SETTLED"
    assert case["payout_marker"] == "PAID"
    assert settlement["owner_payout_wei"] == GLASS
    with direct_vm.expect_revert("already paid or refunded"):
        c.resolve()
    after = c.get_case()
    after_pay = c.get_settlement()
    assert after["payout_marker"] == "PAID"
    assert after["deposit_wei"] == case["deposit_wei"]
    assert after_pay["owner_payout_wei"] == settlement["owner_payout_wei"]
    assert after_pay["tenant_refund_wei"] == settlement["tenant_refund_wei"]


def test_get_settlement_equals_sum_of_triggered(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    _mock_vision(
        direct_vm,
        {"verdict": "SETTLE", "triggered": ["broken_glass", "wall_scuff"]},
    )
    c.resolve()
    settlement = c.get_settlement()
    expected = GLASS + WALL
    assert settlement["owner_payout_wei"] == expected
    assert settlement["tenant_refund_wei"] == MAX_TOTAL - expected
    assert set(settlement["triggered_ids"]) == {"broken_glass", "wall_scuff"}
    # No shadow payout field exists on the case blob.
    assert "owner_payout_wei" not in c.get_case()


def test_invented_id_cannot_pay(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    _mock_vision(
        direct_vm,
        {
            "verdict": "SETTLE",
            "triggered": ["item_99", "broken_glass", "item_99", "not_real"],
        },
    )
    c.resolve()
    settlement = c.get_settlement()
    assert settlement["triggered_ids"] == ["broken_glass"]
    assert settlement["owner_payout_wei"] == GLASS
    assert settlement["tenant_refund_wei"] == MAX_TOTAL - GLASS


def test_settle_empty_triggered_is_full_refund_paid(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    _mock_vision(direct_vm, {"verdict": "SETTLE", "triggered": []})
    c.resolve()
    settlement = c.get_settlement()
    assert settlement["verdict"] == "SETTLE"
    assert settlement["triggered_ids"] == []
    assert settlement["owner_payout_wei"] == 0
    assert settlement["tenant_refund_wei"] == MAX_TOTAL
    assert c.get_case()["payout_marker"] == "PAID"


def test_insufficient_refunds_depositor(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    _fund(direct_vm, c, direct_bob, MAX_TOTAL)
    direct_vm.sender = direct_bob
    c.submit_move_out(MOVE_OUT)
    _mock_vision(
        direct_vm,
        {"verdict": "INSUFFICIENT", "triggered": ["broken_glass"]},
    )
    c.resolve()
    settlement = c.get_settlement()
    assert settlement["verdict"] == "INSUFFICIENT"
    assert settlement["triggered_ids"] == []
    assert settlement["owner_payout_wei"] == 0
    assert settlement["tenant_refund_wei"] == MAX_TOTAL
    assert c.get_case()["payout_marker"] == "REFUNDED"
    assert c.get_case()["status"] == "SETTLED"


def test_withdraw_no_credit_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("no credit"):
        c.withdraw()


def test_zero_value_fund_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("value must be > 0"):
        _fund(direct_vm, c, direct_bob, 0)


def test_cancel_unfunded(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    c = _deploy(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    c.cancel()
    case = c.get_case()
    assert case["status"] == "CANCELLED"
    assert case["payout_marker"] == "NONE"
