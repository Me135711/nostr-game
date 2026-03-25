import time

# Configuration
BLOCK_REWARD = 50  # initial reward in BTC
HALVING_INTERVAL = 210000  # blocks after which reward is halved
MAX_BITCOINS = 21000000  # maximum Bitcoin that can ever exist

# Data storage
miner_stats = {}

# Function to calculate current block reward
def get_current_block_reward(block_number):
    halvings = block_number // HALVING_INTERVAL
    reward = BLOCK_REWARD / (2 ** halvings)
    return reward

# Function to update miner stats
def update_miner_stats(miner_id, hash_rate):
    miner_stats[miner_id] = miner_stats.get(miner_id, {'hash_rate': 0, 'btc_mined': 0})
    miner_stats[miner_id]['hash_rate'] += hash_rate

# Function to distribute Bitcoin
def distribute_bitcoin(block_number):
    total_hash_rate = sum(stat['hash_rate'] for stat in miner_stats.values())
    if total_hash_rate == 0:
        return  # Avoid division by zero
    block_reward = get_current_block_reward(block_number)
    # Distribute reward proportional to hash rate
    for miner_id, stats in miner_stats.items():
        miner_share = (stats['hash_rate'] / total_hash_rate) * block_reward
        stats['btc_mined'] += miner_share
        # Ensure we don't exceed the total Bitcoin cap
        if sum(stats['btc_mined'] for stats in miner_stats.values()) > MAX_BITCOINS:
            raise ValueError("Total Bitcoin cap exceeded!")

# Main mining loop
block_number = 0
while True:
    # Assuming the hash rates are randomly generated for simulation
    for miner_id in range(1, 6):
        update_miner_stats(miner_id, hash_rate=random.randint(1, 100))

    distribute_bitcoin(block_number)
    print(f'Block {block_number} mined! Distribution complete.')
    block_number += 1
    time.sleep(600)  # Sleep for 10 minutes