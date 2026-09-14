import main from "./deploy/001_deploy_wearsettle.ts";
import { createClient } from "genlayer-js";
import { privateKeyToAccount } from "viem/accounts";


async function run() {
  const account = privateKeyToAccount(process.env.GL_PRIVATE_KEY_COVERLOCK_SUBMITTER);
  
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
  console.log(process.env.WEARSETTLE_DEADLINE);

  await main(client);
}
run();
