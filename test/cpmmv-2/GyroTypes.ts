import TokenList from '@balancer-labs/v2-helpers/src/models/tokens/TokenList';
import Vault from '@balancer-labs/v2-helpers/src/models/vault/Vault';
import { SignerWithAddress } from '@nomiclabs/hardhat-ethers/dist/src/signer-with-address';
import { BigNumberish } from './numbers';

export enum WeightedPoolType {
  WEIGHTED_POOL = 0,
  WEIGHTED_POOL_2TOKENS,
  LIQUIDITY_BOOTSTRAPPING_POOL,
  INVESTMENT_POOL,
}

export type RawGyroPoolDeployment = {
  tokens?: TokenList;
  weights?: BigNumberish[];
  sqrts?: BigNumberish[];
  assetManagers?: string[];
  swapFeePercentage?: BigNumberish;
  pauseWindowDuration?: BigNumberish;
  bufferPeriodDuration?: BigNumberish;
  oracleEnabled?: boolean;
  swapEnabledOnStart?: boolean;
  managementSwapFeePercentage?: BigNumberish;
  owner?: SignerWithAddress;
  admin?: SignerWithAddress;
  from?: SignerWithAddress;
  vault?: Vault;
  fromFactory?: boolean;
  poolType?: WeightedPoolType;
};