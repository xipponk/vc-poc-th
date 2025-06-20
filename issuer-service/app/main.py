from fastapi import FastAPI
from web3 import Web3

# --- Configuration ---
# Ganache run inside Docker on the same VM, so we will connect through localhost (127.0.0.1)
GANACHE_URL = "http://127.0.0.1:8545" 
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from Issuer Service!"}

# create an endpoint for blockchain info
# This endpoint will return the chain ID, latest block number, and total accounts
@app.get("/blockchain-info")
def get_blockchain_info():
    if web3.is_connected():
        chain_id = web3.eth.chain_id
        latest_block = web3.eth.block_number
        # normally Ganache will have accounts preloaded, 10 accounts by default
        accounts = web3.eth.accounts
        
        return {
            "status": "Connected to Blockchain",
            "chain_id": chain_id,
            "latest_block_number": latest_block,
            "total_accounts": len(accounts),
            "first_account_address": accounts[0] if accounts else "No accounts found"
        }
    else:
        return {"status": "Failed to connect to Blockchain"}