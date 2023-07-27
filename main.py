"""Use Testnet Bridge (Arbitrum or Optimism -> Goerli)"""

import random

from src import testnet_bridge, sleeping


# In seconds
SLEEP_FROM = 100
SLEEP_TO   = 200

# All values in ETH
AMOUNT_FROM = 0.00008
AMOUNT_TO   = 0.00017
MAX_GAS     = 0.0005  # Gas for Arbitrum
MAX_VALUE   = 0.0005  # Gas for Layer0

RANDOM_WALLETS = True  # Shuffle wallets
FROM_CHAIN     = "Arbitrum"  # Arbitrum or Optimism
WALLETS_PATH   = "data/wallets.txt"  # Path for file with private keys


if __name__ == "__main__":
    with open(WALLETS_PATH, "r") as f:
        WALLETS = [row.strip() for row in f]

    if RANDOM_WALLETS:
        random.shuffle(WALLETS)

    for i, wallet in enumerate(WALLETS):
        testnet_bridge(
            name=str(i),
            private_key=wallet,
            from_chain=FROM_CHAIN,
            max_bridge=random.uniform(AMOUNT_FROM, AMOUNT_TO),
            max_gas=MAX_GAS,
            max_value=MAX_VALUE
        )

        sleeping(SLEEP_FROM, SLEEP_TO)
