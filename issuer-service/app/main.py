import json
from fastapi import FastAPI, HTTPException
from web3 import Web3
from pydantic import BaseModel
import os

# --- Configuration ---
GANACHE_URL = "http://127.0.0.1:8545"
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

# Load the contract artifact (ABI and Address)
artifact_path = os.path.join(os.path.dirname(__file__), 'contract_artifact.json')
with open(artifact_path, 'r') as f:
    contract_artifact = json.load(f)

contract_address = contract_artifact['address']
contract_abi = contract_artifact['abi']

# Create a contract instance
credential_registry_contract = web3.eth.contract(
    address=contract_address,
    abi=contract_abi
)

# Set the default account for sending transactions
web3.eth.default_account = web3.eth.accounts[0]


app = FastAPI()

# --- Pydantic Models for Request Body ---
class IssuerRegistration(BaseModel):
    issuer_address: str
    issuer_name: str


# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Hello from Issuer Service!"}

@app.get("/blockchain-info")
def get_blockchain_info():
    if web3.is_connected():
        accounts = web3.eth.accounts
        return {
            "status": "Connected to Blockchain",
            "chain_id": web3.eth.chain_id,
            "latest_block_number": web3.eth.block_number,
            "contract_address": contract_address,
            "contract_owner": credential_registry_contract.functions.owner().call(),
            "ganache_accounts": accounts
        }
    else:
        return {"status": "Failed to connect to Blockchain"}

@app.post("/register-issuer")
def register_issuer(issuer_data: IssuerRegistration):
    try:
        tx_hash = credential_registry_contract.functions.addIssuer(
            issuer_data.issuer_address,
            issuer_data.issuer_name
        ).transact()
        
        web3.eth.wait_for_transaction_receipt(tx_hash)
        
        return {
            "status": "success",
            "message": f"Issuer '{issuer_data.issuer_name}' registered successfully.",
            "transaction_hash": tx_hash.hex()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- NEW ENDPOINT TO CHECK A SPECIFIC ISSUER ---
@app.get("/issuers/{issuer_address}")
def get_issuer_status(issuer_address: str):
    try:
        # Call the 'isIssuerRegistered' view function on our Smart Contract
        is_registered = credential_registry_contract.functions.isIssuerRegistered(issuer_address).call()
        
        # Call the 'issuers' public mapping to get the name
        if is_registered:
            issuer_info = credential_registry_contract.functions.issuers(issuer_address).call()
            issuer_name = issuer_info[0] # The name is the first element in the struct
            return {"address": issuer_address, "name": issuer_name, "is_registered": True}
        else:
            return {"address": issuer_address, "is_registered": False}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- NEW ENDPOINT TO LIST ALL REGISTERED ISSUERS ---
@app.get("/issuers")
def get_all_issuers():
    # NOTE: Smart contracts don't easily allow iterating through a mapping.
    # For this POC, we will iterate through the known Ganache accounts and check each one.
    registered_issuers = []
    all_ganache_accounts = web3.eth.accounts
    
    for account in all_ganache_accounts:
        is_registered = credential_registry_contract.functions.isIssuerRegistered(account).call()
        if is_registered:
            issuer_info = credential_registry_contract.functions.issuers(account).call()
            registered_issuers.append({
                "address": account,
                "name": issuer_info[0]
            })
            
    return {"registered_issuers": registered_issuers}