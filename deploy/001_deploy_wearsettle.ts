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
  const resolveDeadline = Number(
    process.env.WEARSETTLE_RESOLVE_DEADLINE || DEADLINE,
  );
  const inventory = process.env.WEARSETTLE_INVENTORY || INVENTORY;
  const skipResolve = process.env.WEARSETTLE_SKIP_RESOLVE === "1";

  // genlayer deploy compiles the TS to a tmp dir; resolve back to project root
  const projectRoot = process.env.WEARSETTLE_PROJECT_ROOT ||
    new URL("../", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1").replace(/\//g, "\\");
  const contractFile = `${projectRoot}contracts\\wearsettle.py`;
  const code = new Uint8Array(readFileSync(contractFile));

  const { CalldataAddress } = await import("genlayer-js/types");
  const tenantBytes = new Uint8Array(20);
  const tHex = tenant.startsWith("0x") ? tenant.slice(2) : tenant;
  for (let i = 0; i < 20; i++) tenantBytes[i] = parseInt(tHex.slice(i*2, i*2+2), 16);
  const tenantArg = new CalldataAddress(tenantBytes);

  const deployHash = await client.deployContract({
    code,
    args: [tenantArg, moveIn, deadline, resolveDeadline, inventory],
    fees: {
      feeValue: "100000000000000000",
      distribution: {
        leaderTimeunitsAllocation: "600",
        validatorTimeunitsAllocation: "600",
        rotations: ["0"],
        executionBudgetPerRound: "10000000000000000",
        maxPriceGenPerTimeUnit: "10",
        storageFeeMaxGasPrice: "1000000000",
        receiptFeeMaxGasPrice: "1000000000",
      },
    },
  });
  const deployTx = await waitTx(client, deployHash, 80);
  if (!isSuccessful(deployTx)) {
    console.error("Deploy failed. Tx:", JSON.stringify(deployTx, null, 2));
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

  const feesConfig = {
    feeValue: "100000000000000000",
    distribution: {
      leaderTimeunitsAllocation: "600",
      validatorTimeunitsAllocation: "600",
      rotations: ["0"],
      executionBudgetPerRound: "10000000000000000",
      maxPriceGenPerTimeUnit: "10",
      storageFeeMaxGasPrice: "1000000000",
      receiptFeeMaxGasPrice: "1000000000",
    },
  };

  const fundHash = await client.writeContract({
    address: contractAddress,
    functionName: "fund_deposit",
    args: [],
    value: MAX_TOTAL,
    fees: feesConfig,
  });
  const fundTx = await waitTx(client, fundHash, 80);
  console.log("FUNDED", { fundHash, ok: isSuccessful(fundTx) });

  const moveHash = await client.writeContract({
    address: contractAddress,
    functionName: "submit_move_out",
    args: [process.env.WEARSETTLE_MOVE_OUT || MOVE_OUT_404],
    fees: feesConfig,
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
      fees: feesConfig,
    });
    const resolveTx = await waitTx(client, resolveHash, 180);
    console.log("RESOLVE_TX_FULL", JSON.stringify(resolveTx, null, 2));
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
        fees: feesConfig,
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
    network: "studio-dev",
    chainId: 61997,
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
