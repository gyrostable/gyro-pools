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
          evmVersion: "berlin",
          optimizer: {
            enabled: true,
            runs: 200,
          },
          // remappings: ["@balancer-labs/v2-solidity-utils/contracts/helpers/TemporarilyPausable.sol=contracts/TemporarilyPausable.sol"],
        },
      },
    ],
    // overrides: hardhatBaseConfig.overrides("xxx"),
  },
  networks: {
    mainnet: {
      url: `https://mainnet.infura.io/v3/${process.env.WEB3_INFURA_PROJECT_ID}`,
    },
    polygon: {
      url: "https://polygon-rpc.com",
    },
    optimisticEthereum: {
      url: "https://mainnet.optimism.io",
    },
    arbitrumOne: {
      url: "https://arb1.arbitrum.io/rpc",
    },
    zkevm: {
      url: "https://zkevm-rpc.com",
    },
    hardhat: {
      chainId: 137,
      forking: {
        url: "https://polygon-mainnet.g.alchemy.com/v2/5RhbxHGv1PCMTnG9iZRQ9T7tzYIuy1eS",
      },
    },
  },
  etherscan: {
    apiKey: {
      mainnet: process.env.ETHERSCAN_TOKEN || "",
      polygon: process.env.POLYGONSCAN_TOKEN || "",
      optimisticEthereum: process.env.OPTISCAN_TOKEN || "",
      arbitrumOne: process.env.ARBISCAN_TOKEN || "",
      zkevm: process.env.ZKEVM_TOKEN || "",
    },
    customChains: [
      {
        network: "zkevm",
        chainId: 1101,
        urls: {
          apiURL: "https://api-zkevm.polygonscan.com/api",
          browserURL: "https://zkevm.polygonscan.com/",
        },
      },
    ],
  },
};

export default config;
