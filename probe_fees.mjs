import { createClient, chains } from "genlayer-js";
import { privateKeyToAccount } from "viem/accounts";
import { readFileSync } from "node:fs";

const pk = readFileSync(".env", "utf8")
  .split("\n")
  .find(l => l.startsWith("GL_PRIVATE_KEY_COVERLOCK_SUBMITTER="))
  ?.split("=")[1]?.trim();

const account = privateKeyToAccount(pk);

// studio-dev is 61997 - same structure as studionet (61999) but different id/url
const studioDev = {
  ...chains.studionet,
  id: 61997,
  name: "Studio Devnet",
  rpcUrls: {
    default: { http: ["https://studio-dev.genlayer.com/api"] }
  }
};

const client = createClient({
  chain: studioDev,
  account
});

async function run() {
  try {
    // Try reading current fee policy directly from the RPC
    const feePolicy = await client.request({
      method: "gen_getFeePolicy",
      params: []
    });
    console.log("Fee policy (gen_getFeePolicy):", JSON.stringify(feePolicy, (k, v) => typeof v === "bigint" ? v.toString() : v, 2));
  } catch (e) {
    console.log("gen_getFeePolicy failed:", e.message);
  }
  
  try {
    // Try getting the consensus contract info
    const allMethods = await client.request({
      method: "rpc_methods",
      params: []
    });
    console.log("RPC methods:", allMethods);
  } catch (e) {
    console.log("rpc_methods failed:", e.message);
  }

  // Try to explicitly pass a nonzero feeValue
  try {
    const code = readFileSync("contracts/wearsettle.py", "utf8");
    const tenantAddr = "0xBb4e0fD1CEaC9F8db17242CF86decDcdd45FA48a";
    // Pass a nonzero feeValue explicitly through fees object
    const deployHash = await client.deployContract({
      code,
      args: [tenantAddr, "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg", 2592000, 2592000, "{}"],
      fees: { feeValue: "100000000000000" }  // 0.0001 GEN
    });
    console.log("Deploy hash:", deployHash);
  } catch (e) {
    console.error("Deploy error:", e.message);
  }
}
run();
