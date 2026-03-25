import time
import random

class BitcoinMining:
    def __init__(self, cap=21000000):
        self.total_mined = 0
        self.cap = cap
        self.block_reward = 50  # Starting block reward
        self.blocks_mined = 0

    def mine_block(self, player_hashrate):
        if self.total_mined < self.cap:
            # Simulate mining
            time.sleep(600)  # 10 minutes
            self.blocks_mined += 1
            self.total_mined += self.block_reward
            self.distribute_rewards(player_hashrate)
            self.check_halving()

    def distribute_rewards(self, player_hashrate):
        # Placeholder for the example of calculating rewards based on hash rate
        proportion = player_hashrate / sum(player_hashrates)
        reward = self.block_reward * proportion
        print(f'Reward distributed: {reward} BTC based on a hash rate of {player_hashrate}')

    def check_halving(self):
        if self.blocks_mined % 210000 == 0:
            self.block_reward /= 2
            print(f'Block reward halved to: {self.block_reward} BTC')

# Example player hashrates
player_hashrates = [random.randint(1, 100) for _ in range(5)]  
# Example usage
mining = BitcoinMining()  
for hashrate in player_hashrates:
    mining.mine_block(hashrate)