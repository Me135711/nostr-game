import sqlite3
import time
from datetime import datetime
import requests
from typing import Dict, Set, Optional

# Nostr relay configuration
RELAYS = [
    "wss://relay.damus.io",
    "wss://relay.nostr.band",
    "wss://nos.lol",
]

class NostrHashRewardBot:
    def __init__(self, npub: str, db_path: str = "nostr_game.db"):
        """
        Initialize the Nostr hash reward bot.
        
        Args:
            npub: Your Nostr public key (npub format)
            db_path: Path to SQLite database
        """
        self.npub = npub
        self.db_path = db_path
        self.hash_reward = 1  # Hash rate awarded per !hash command
        self.fiat_cost = 10000  # Fiat required per hash purchase
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                pubkey TEXT PRIMARY KEY,
                npub TEXT UNIQUE,
                fiat_balance INTEGER DEFAULT 0,
                hash_rate INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add hash_rate column if it doesn't exist
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN hash_rate INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create hash_purchases table to track individual purchases
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hash_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pubkey TEXT,
                post_id TEXT,
                post_author TEXT,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hash_amount INTEGER,
                fiat_spent INTEGER,
                UNIQUE(pubkey, post_id)
            )
        ''')
        
        # Create transactions table for audit trail
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pubkey TEXT,
                transaction_type TEXT,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def npub_to_hex(self, npub: str) -> str:
        """
        Convert npub format to hex pubkey.
        
        Args:
            npub: Nostr public key in npub format
            
        Returns:
            Hex format pubkey
        """
        try:
            import base64
            # Remove 'npub1' prefix and decode
            data = base64.b32decode(npub[5:].upper() + "======")
            return data[:-4].hex()
        except Exception as e:
            raise ValueError(f"Invalid npub format: {e}")
    
    def get_user_balance(self, pubkey_hex: str) -> Dict[str, int]:
        """
        Get a user's current fiat balance and hash rate.
        
        Args:
            pubkey_hex: User's pubkey in hex format
            
        Returns:
            Dict with 'fiat_balance' and 'hash_rate'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT fiat_balance, hash_rate FROM users WHERE pubkey = ?',
            (pubkey_hex,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'fiat_balance': result[0], 'hash_rate': result[1]}
        return {'fiat_balance': 0, 'hash_rate': 0}
    
    def get_my_posts(self) -> Dict[str, dict]:
        """
        Fetch your posts from Nostr relays.
        
        Returns:
            Dict with post IDs as keys and post data as values
        """
        my_posts = {}
        my_hex = self.npub_to_hex(self.npub)
        
        try:
            for relay in RELAYS:
                try:
                    posts = self._query_relay_posts(relay, my_hex)
                    my_posts.update(posts)
                except Exception as e:
                    print(f"Error querying {relay}: {e}")
                    continue
        except Exception as e:
            print(f"Error fetching posts: {e}")
        
        return my_posts
    
    def _query_relay_posts(self, relay_url: str, author_hex: str) -> Dict[str, dict]:
        """
        Query a relay for posts from a specific author.
        
        Args:
            relay_url: WebSocket URL of the relay
            author_hex: Author's pubkey in hex format
            
        Returns:
            Dict of posts with event IDs as keys
        """
        posts = {}
        
        try:
            url = relay_url.replace('wss://', 'https://').replace('ws://', 'http://')
            params = {
                'limit': 100,
                'authors': author_hex,
                'kinds': '1'  # Kind 1 = short text note
            }
            
            response = requests.get(f"{url}/api/v1/events", params=params, timeout=5)
            if response.status_code == 200:
                events = response.json()
                for event in events:
                    posts[event.get('id')] = {
                        'author': event.get('pubkey'),
                        'content': event.get('content', ''),
                        'created_at': event.get('created_at'),
                        'tags': event.get('tags', [])
                    }
        except Exception as e:
            print(f"Error in relay query: {e}")
        
        return posts
    
    def get_replies_to_post(self, post_id: str) -> Dict[str, dict]:
        """
        Get all replies to a specific post.
        
        Args:
            post_id: The post event ID
            
        Returns:
            Dict of reply events
        """
        replies = {}
        
        try:
            for relay in RELAYS:
                try:
                    relay_replies = self._query_relay_replies(relay, post_id)
                    replies.update(relay_replies)
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error fetching replies: {e}")
        
        return replies
    
    def _query_relay_replies(self, relay_url: str, post_id: str) -> Dict[str, dict]:
        """
        Query a relay for replies to a specific post.
        
        Args:
            relay_url: Relay URL
            post_id: Post event ID
            
        Returns:
            Dict of reply events
        """
        replies = {}
        
        try:
            url = relay_url.replace('wss://', 'https://').replace('ws://', 'http://')
            params = {
                'limit': 1000,
                'kinds': '1',
                'e': post_id  # Filter for replies to this event
            }
            
            response = requests.get(f"{url}/api/v1/events", params=params, timeout=5)
            if response.status_code == 200:
                events = response.json()
                for event in events:
                    replies[event.get('id')] = {
                        'pubkey': event.get('pubkey'),
                        'content': event.get('content', ''),
                        'created_at': event.get('created_at'),
                        'tags': event.get('tags', [])
                    }
        except Exception as e:
            pass
        
        return replies
    
    def add_user_if_not_exists(self, pubkey_hex: str, npub: str = None) -> None:
        """Add user to database if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT OR IGNORE INTO users (pubkey, npub, fiat_balance, hash_rate) VALUES (?, ?, ?, ?)',
            (pubkey_hex, npub, 0, 0)
        )
        
        conn.commit()
        conn.close()
    
    def process_hash_command(self, player_pubkey_hex: str, post_id: str, player_npub: str = None) -> bool:
        """
        Process a !hash command from a player.
        Check fiat balance, deduct cost, award hash rate.
        Allow unlimited purchases as long as they have enough fiat.
        
        Args:
            player_pubkey_hex: Player's pubkey in hex format
            post_id: The post ID they're replying to
            player_npub: Player's npub (optional)
            
        Returns:
            True if hash was awarded, False if insufficient fiat or error
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Add user if doesn't exist
            self.add_user_if_not_exists(player_pubkey_hex, player_npub)
            
            # Get current balance
            cursor.execute(
                'SELECT fiat_balance, hash_rate FROM users WHERE pubkey = ?',
                (player_pubkey_hex,)
            )
            result = cursor.fetchone()
            
            if not result:
                print(f"Error: User not found {player_pubkey_hex[:16]}...")
                return False
            
            current_fiat, current_hash = result
            
            # Check if player has enough fiat
            if current_fiat < self.fiat_cost:
                print(f"✗ Player {player_pubkey_hex[:16]}... needs {self.fiat_cost} fiat but only has {current_fiat}")
                return False
            
            # Deduct fiat and award hash
            new_fiat = current_fiat - self.fiat_cost
            new_hash = current_hash + self.hash_reward
            
            cursor.execute(
                'UPDATE users SET fiat_balance = ?, hash_rate = ? WHERE pubkey = ?',
                (new_fiat, new_hash, player_pubkey_hex)
            )
            
            # Record the purchase
            cursor.execute(
                '''INSERT INTO hash_purchases (pubkey, post_id, post_author, hash_amount, fiat_spent)
                   VALUES (?, ?, ?, ?, ?)''',
                (player_pubkey_hex, post_id, self.npub_to_hex(self.npub), self.hash_reward, self.fiat_cost)
            )
            
            # Record transaction
            cursor.execute(
                '''INSERT INTO transactions (pubkey, transaction_type, amount, reason)
                   VALUES (?, ?, ?, ?)''',
                (player_pubkey_hex, 'hash_purchase', -self.fiat_cost, f'Purchased {self.hash_reward} hash rate')
            )
            
            conn.commit()
            print(f"✓ Player {player_pubkey_hex[:16]}... purchased 1 hash rate!")
            print(f"  Fiat: {current_fiat} → {new_fiat} | Hash Rate: {current_hash} → {new_hash}")
            return True
            
        except sqlite3.IntegrityError:
            # Unique constraint - player already bought on this post
            print(f"Player {player_pubkey_hex[:16]}... already purchased hash for this post")
            conn.rollback()
            return False
        except Exception as e:
            print(f"Error processing hash command: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def run(self) -> None:
        """Main bot loop - check for !hash commands in replies and process them."""
        print(f"Starting Nostr Hash Reward Bot for {self.npub}")
        print(f"Hash rate reward: {self.hash_reward} per command")
        print(f"Fiat cost: {self.fiat_cost} per command")
        print(f"Database: {self.db_path}\n")
        
        try:
            print("Fetching your posts from Nostr relays...")
            my_posts = self.get_my_posts()
            
            if not my_posts:
                print("No posts found.")
                print("Note: This script uses a simplified method. For production, use:")
                print("  - nostr-py library (https://github.com/nostr-protocol/nostr-py)")
                print("  - websockets library for WebSocket relay connections")
                return
            
            print(f"Found {len(my_posts)} of your posts")
            
            total_purchases = 0
            total_fiat_collected = 0
            
            # Check each post for replies with !hash command
            for post_id, post_data in my_posts.items():
                print(f"\nChecking post: {post_id[:16]}...")
                
                replies = self.get_replies_to_post(post_id)
                
                for reply_id, reply_data in replies.items():
                    content = reply_data.get('content', '').strip()
                    
                    # Check if reply contains !hash command
                    if '!hash' in content:
                        player_pubkey = reply_data.get('pubkey')
                        
                        if self.process_hash_command(player_pubkey, post_id):
                            total_purchases += 1
                            total_fiat_collected += self.fiat_cost
            
            print(f"\n--- Session Summary ---")
            print(f"Posts checked: {len(my_posts)}")
            print(f"Hash purchases processed: {total_purchases}")
            print(f"Total fiat collected: {total_fiat_collected}")
            self.print_leaderboard()
            
        except Exception as e:
            print(f"Error in bot run: {e}")
    
    def print_leaderboard(self) -> None:
        """Print top users by hash rate and fiat balance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Top by hash rate
        cursor.execute(
            '''SELECT pubkey, npub, hash_rate, fiat_balance FROM users 
               ORDER BY hash_rate DESC LIMIT 10'''  
        )
        hash_results = cursor.fetchall()
        
        # Top by fiat balance
        cursor.execute(
            '''SELECT pubkey, npub, fiat_balance, hash_rate FROM users 
               ORDER BY fiat_balance DESC LIMIT 10'''  
        )
        fiat_results = cursor.fetchall()
        
        conn.close()
        
        if hash_results:
            print("\n--- Top 10 Users by Hash Rate ---")
            for i, (pubkey, npub, hash_rate, fiat_balance) in enumerate(hash_results, 1):
                print(f"{i}. {pubkey[:16]}... | Hash Rate: {hash_rate} | Fiat: {fiat_balance}")
        
        if fiat_results:
            print("\n--- Top 10 Users by Fiat Balance ---")
            for i, (pubkey, npub, fiat_balance, hash_rate) in enumerate(fiat_results, 1):
                print(f"{i}. {pubkey[:16]}... | Fiat: {fiat_balance} | Hash Rate: {hash_rate}")


if __name__ == "__main__":
    # Configuration
    YOUR_NPUB = "npub1..."  # Replace with your actual npub
    DB_PATH = "nostr_game.db"
    
    # Validate npub format
    if not YOUR_NPUB.startswith("npub1"):
        print("ERROR: Invalid npub format. Must start with 'npub1'")
        exit(1)
    
    # Run bot
    bot = NostrHashRewardBot(YOUR_NPUB, DB_PATH)
    bot.run()