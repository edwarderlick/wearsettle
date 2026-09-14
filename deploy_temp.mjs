import { createClient } from "genlayer-js";
import { privateKeyToAccount } from "viem/accounts";
import { readFileSync } from "node:fs";


async function main() {
  const account = privateKeyToAccount(process.env.GL_PRIVATE_KEY_COVERLOCK_SUBMITTER);
  const tenant = privateKeyToAccount(process.env.GL_PRIVATE_KEY_CONCORD_BOB).address;
  
  const client = createClient({
    chain: {
      id: 61997,
      name: "Studio Devnet",
      rpcUrls: {
        default: { http: ["https://studio-dev.genlayer.com/api"] }
      }
    },
    account
  });

  const contractCode = readFileSync("contracts/wearsettle.py", "utf-8");
  
  try {
    const hash = await client.deployContract({
      code: contractCode,
      args: [
        tenant,
        "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg",
        2592000n,
        2592000n,
        "{}"
      ],
      value: 100000n,
      leaderOnly: false
    });
    console.log("Deployed with hash:", hash);
  } catch (e) {
    console.error(e);
  }
}

main();
