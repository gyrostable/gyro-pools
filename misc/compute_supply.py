### Calibrate the WETH/WBTC 2-CLP pool
# set the following
p_eth = 1690
p_btc = 23079
sqrt_alpha = 0.2236 # alpha = 0.05
sqrt_beta = 0.2916 # beta = 0.085

L_init = 1e-8 # can set to w/e, choose x,y are small

px = p_eth / p_btc
x = L_init * (1/px **(1/2) - 1/sqrt_beta)
y = L_init * (px **(1/2) - sqrt_alpha)
S_init = L_init * 2 
p_bpt = (x*p_eth + y*p_btc) / S_init

# x is amount of WETH, y is amount of WBTC, p_bbt is initial price of bpt token
print(x,y,p_bpt)


### Calibrate the TUSD/USDC/DAI 3-CLP pool
# set the following
px = 0.9989 # p_tusd_usdc
py = 1 # p_dai_usdc
cbrt_alpha = 0.9995

assert(px * py >= cbrt_alpha**3)
assert(px / py**2 >= cbrt_alpha**3)
assert(py / px**2 >= cbrt_alpha**3)

L_init = 1e-2 # can set to w/e, choose so that x,y,z are small

cbrtpxpy = (px * py)**(1/3)
x = L_init * (cbrtpxpy / px - cbrt_alpha)
y = L_init * (cbrtpxpy / py - cbrt_alpha)
z = L_init * (cbrtpxpy - cbrt_alpha)
S_init = L_init * 3
p_bpt = (px * x + y + z) / S_init

# x is amount of TUSD, y is amount of DAI, z is amount of USDC, p_bbt is initial price of bpt token
print("TUSD", x * 10 ** 18)
print("DAI", y * 10 ** 18)
print("USDC", z * 10 ** 6)
print("price BPT", p_bpt * 10 ** 18)
