import { HardhatUserConfig } from "hardhat/config";
import "@nomiclabs/hardhat-etherscan";
import "@nomiclabs/hardhat-waffle";
import "@typechain/hardhat";
import "hardhat-gas-reporter";
import "solidity-coverage";
import overrideQueryFunctions from "./misc/overrideQueryFunctions";
import { task } from "hardhat/config";
import { TASK_COMPILE } from "hardhat/builtin-tasks/task-names";
// import { hardhatBaseConfig } from "@balancer-labs/v2-common";

task(TASK_COMPILE).setAction(overrideQueryFunctions);

const config: HardhatUserConfig = {
  solidity: {
    compilers: [
      {
        version: "0.7.6",
        settings: {
          optimizer: {
            enabled: true,
            runs: 200,
          },
        },
      },
    ],
    // overrides: hardhatBaseConfig.overrides("xxx"),
  },
  networks: {
    polygon: {
      url: "https://polygon-rpc.com",
    },
    hardhat: {
      chainId: 137,
      forking: {
        url: "https://polygon-mainnet.g.alchemy.com/v2/5RhbxHGv1PCMTnG9iZRQ9T7tzYIuy1eS",
      },
    },
  },
  etherscan: {
    apiKey: process.env.POLYGONSCAN_TOKEN || "",
  },
};

export default config;
