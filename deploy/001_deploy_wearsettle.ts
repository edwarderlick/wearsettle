import { readFileSync, writeFileSync } from "node:fs";
import type { DecodedDeployData, GenLayerClient } from "genlayer-js/types";

function isSuccessful(tx: any): boolean {
  const exec = String(tx?.txExecutionResultName || tx?.executionResult || "").toLowerCase();
  if (exec.includes("fail") || exec.includes("error") || exec.includes("revert")) {
    return false;
  }
  return true;
}

const MOVE_IN =
  "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg";
const MOVE_OUT_404 =
  "https://upload.wikimedia.org/wikipedia/commons/does-not-exist-wearsettle-404.jpg";
const DEADLINE = 2_592_000;
const MAX_TOTAL = 350000000000000n;
const INVENTORY = JSON.stringify([
  { id: "wall_scuff", label: "Wall scuff or hole", max_charge_wei: 100000000000000 },
  { id: "missing_remote", label: "TV remote present", max_charge_wei: 50000000000000 },
  {
    id: "broken_glass",
    label: "Window or glass pane intact",
    max_charge_wei: 200000000000000,
  },
]);

async function waitTx(client: GenLayerClient<any>, hash: any, retries = 80) {
  const transaction = await client.waitForTransactionReceipt({
    hash,
    retries,
    interval: 4000,
  });
  return transaction;
}

export default async function main(client: GenLayerClient<any>) {
  const tenant =
    process.env.WEARSETTLE_TENANT ||
    "0x441a6da5d7d61d6f289c024196963da6f5da010a";
  const moveIn = process.env.WEARSETTLE_MOVE_IN || MOVE_IN;
  const deadline = Number(process.env.WEARSETTLE_DEADLINE || DEADLINE);
  const inventory = process.env.WEARSETTLE_INVENTORY || INVENTORY;
  const skipResolve = process.env.WEARSETTLE_SKIP_RESOLVE === "1";

  const code = new Uint8Array(
    readFileSync(new URL("../contracts/wearsettle.py", import.meta.url)),
  );

  const deployHash = await client.deployContract({
    code,
    args: [tenant, moveIn, deadline, inventory],
  });
  const deployTx = await waitTx(client, deployHash, 80);
  if (!isSuccessful(deployTx)) {
    throw new Error(
      `WearSettle deploy failed: ${deployTx.statusName} / ${deployTx.txExecutionResultName}`,
    );
  }
  const decoded = deployTx.txDataDecoded as DecodedDeployData | undefined;
  const contractAddress = decoded?.contractAddress ?? deployTx.recipient;
  if (!contractAddress) {
    throw new Error("Finalized deployment has no contract address");
  }
  console.log("DEPLOYED", { deployHash, contractAddress });

  const fundHash = await client.writeContract({
    address: contractAddress,
    functionName: "fund_deposit",
    args: [],
    value: MAX_TOTAL,
  });
  const fundTx = await waitTx(client, fundHash, 80);
  console.log("FUNDED", { fundHash, ok: isSuccessful(fundTx) });

  const moveHash = await client.writeContract({
    address: contractAddress,
    functionName: "submit_move_out",
    args: [process.env.WEARSETTLE_MOVE_OUT || MOVE_OUT_404],
  });
  const moveTx = await waitTx(client, moveHash, 80);
  console.log("MOVEOUT", { moveHash, ok: isSuccessful(moveTx) });

  let resolveHash: any = null;
  let secondHash: any = null;
  let settlement: any = null;
  let caseAfter: any = null;

  if (!skipResolve) {
    resolveHash = await client.writeContract({
      address: contractAddress,
      functionName: "resolve",
      args: [],
    });
    const resolveTx = await waitTx(client, resolveHash, 180);
    console.log("RESOLVE", {
      resolveHash,
      ok: isSuccessful(resolveTx),
      status: resolveTx.statusName,
      exec: resolveTx.txExecutionResultName,
    });

    caseAfter = await client.readContract({
      address: contractAddress,
      functionName: "get_case",
      args: [],
    });
    settlement = await client.readContract({
      address: contractAddress,
      functionName: "get_settlement",
      args: [],
    });
    console.log("CASE", caseAfter);
    console.log("SETTLEMENT", settlement);

    try {
      secondHash = await client.writeContract({
        address: contractAddress,
        functionName: "resolve",
        args: [],
      });
      const secondTx = await waitTx(client, secondHash, 40);
      console.log("SECOND_RESOLVE", {
        secondHash,
        ok: isSuccessful(secondTx),
        status: secondTx.statusName,
        exec: secondTx.txExecutionResultName,
      });
    } catch (err) {
      console.log("SECOND_RESOLVE_THREW", String(err));
    }
  }

  const record = {
    network: "studionet",
    chainId: 61999,
    contractAddress,
    deployHash,
    fundHash,
    moveHash,
    resolveHash,
    secondHash,
    tenant,
    moveIn,
    caseAfter,
    settlement,
  };
  writeFileSync(
    "deploy-result.json",
    JSON.stringify(
      record,
      (_key, value) => (typeof value === "bigint" ? value.toString() : value),
      2,
    ),
  );
  console.log("WearSettle deployed", record);
  return contractAddress;
}
