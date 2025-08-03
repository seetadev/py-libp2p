import {
  FusionSDK,
  NetworkEnum,
  OrderStatus,
  PrivateKeyProviderConnector,
  Web3Like
} from "@1inch/fusion-sdk";
import { computeAddress, formatUnits, JsonRpcProvider } from "ethers";

export class FusionClient {
  private sdk: FusionSDK;
  private walletAddress: string;

  constructor(
    privateKey: string,
    rpcUrl: string,
    network: NetworkEnum,
    devPortalKey: string
  ) {
    const ethersProvider = new JsonRpcProvider(rpcUrl);

    const connector: Web3Like = {
      eth: {
        call(tx) {
          return ethersProvider.call(tx);
        }
      },
      extend(): void {}
    };

    const providerConnector = new PrivateKeyProviderConnector(privateKey, connector);

    this.walletAddress = computeAddress(privateKey);

    this.sdk = new FusionSDK({
      url: "https://api.1inch.dev/fusion",
      network,
      blockchainProvider: providerConnector,
      authKey: devPortalKey
    });
  }

  async createAndSubmitOrder(
    fromToken: string,
    toToken: string,
    amount: string,
    tokenDecimals: number = 18
  ): Promise<string> {
    const params = {
      fromTokenAddress: fromToken,
      toTokenAddress: toToken,
      amount,
      walletAddress: this.walletAddress,
      source: "p2p-intent-demo"
    };

    const quote = await this.sdk.getQuote(params);
    const presetKey = quote.recommendedPreset;

    if (!presetKey || !quote.presets || !quote.presets[presetKey]) {
    throw new Error("Missing recommended auction parameters");
    }

    const preset = quote.presets[presetKey];


    console.log("Auction range:", {
      start: formatUnits(preset.auctionStartAmount, tokenDecimals),
      end: formatUnits(preset.auctionEndAmount, tokenDecimals)
    });

    const order = await this.sdk.createOrder(params);
    const result = await this.sdk.submitOrder(order.order, order.quoteId);

    console.log("Submitted OrderHash:", result.orderHash);
    return result.orderHash;
  }

  async pollForStatus(orderHash: string) {
    const start = Date.now();

    while (true) {
      const status = await this.sdk.getOrderStatus(orderHash);
      const state = status.status;

      if (state === OrderStatus.Filled) {
        console.log("Filled", status.fills);
        break;
      } else if (state === OrderStatus.Expired) {
        console.log("Order Expired");
        break;
      } else if (state === OrderStatus.Cancelled) {
        console.log("Order Cancelled");
        break;
      }

      await new Promise((r) => setTimeout(r, 2000));
    }

    console.log("⏱ Order executed in", (Date.now() - start) / 1000, "seconds");
  }
}
