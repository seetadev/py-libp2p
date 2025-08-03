import { FusionClient } from "./fusion";
import { NetworkEnum } from "@1inch/fusion-sdk";

const PRIVATE_KEY = process.env.PRIVATE_KEY!;
const NODE_URL = process.env.RPC_URL!;
const API_KEY = process.env.DEV_PORTAL_KEY!;

async function run() {
  const fusion = new FusionClient(PRIVATE_KEY, NODE_URL, NetworkEnum.ETHEREUM, API_KEY);
  const orderHash = await fusion.createAndSubmitOrder(
    "0xTokenA",  // fromToken
    "0xTokenB",  // toToken
    "1000000000000000000"
  );
  await fusion.pollForStatus(orderHash);
}

run();
