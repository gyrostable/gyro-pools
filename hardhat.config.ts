import { HardhatUserConfig } from "hardhat/config";
import "@nomiclabs/hardhat-etherscan";
import "@nomiclabs/hardhat-waffle";
import "@typechain/hardhat";
import "hardhat-gas-reporter";
import "solidity-coverage";

const config: HardhatUserConfig = {
  solidity: {
    compilers: [
      {
        version: "0.7.1",
        settings: {
          optimizer: {
            enabled: true,
            runs: 9999,
          },
        },
      },
    ],
    overrides: {
      "@balancer-labs/v2-vault/contracts/Vault.sol": {
        version: "0.7.1",
        settings: {
          optimizer: {
            enabled: true,
            runs: 1500,
          },
        },
      },
    },
  },
};

export default config;
