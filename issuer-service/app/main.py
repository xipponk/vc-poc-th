import json
from fastapi import FastAPI, HTTPException
from web3 import Web3
from pydantic import BaseModel
import os
from datetime import datetime, timedelta
import base64
from eth_keys.main import PrivateKey
from jose import jwt, jws
from jose.constants import ALGORITHMS
from jose.utils import base64url_encode

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

# --- FOR POC ONLY: Ganache provides pre-funded accounts with known private keys ---
# We will use these to sign our credentials.
# WARNING: Never expose private keys like this in a real application!
GANACHE_PRIVATE_KEYS = [
    "0x41357af61227854c62afe328dfb4c7030b72953cade8e0c4407b44379786b779", # Corresponds to web3.eth.accounts[0]
    "0x1904b9fd8a0009c914bf506c2974747273029609beeaef3b82d48a0f02d9eb49", # Corresponds to web3.eth.accounts[1]
    "0x59b1180628225849bfb987e189c0199d77324cd3fab0db91a36eaa0628307223", # Corresponds to web3.eth.accounts[2]
    "0x0e2c881f52aff51a81c3624f350c44a8c4ee47310296486e2ecefc905520ceec", # Corresponds to web3.eth.accounts[3]
]


app = FastAPI()

# --- Pydantic Models for Request Body ---
class IssuerRegistration(BaseModel):
    issuer_address: str
    issuer_name: str

class CredentialIssuanceRequest(BaseModel):
    issuer_account_index: int 
    student_id: str
    student_name: str
    degree_name: str
    major: str

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


@app.post("/credentials/issue")
def issue_credential(request: CredentialIssuanceRequest):
    # 1. Select the issuer's identity based on the request
    try:
        issuer_address = web3.eth.accounts[request.issuer_account_index]
        issuer_private_key_hex = GANACHE_PRIVATE_KEYS[request.issuer_account_index]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid issuer_account_index")

    # 2. Check if this issuer is registered in our Smart Contract
    is_registered = credential_registry_contract.functions.isIssuerRegistered(issuer_address).call()
    if not is_registered:
        raise HTTPException(status_code=400, detail=f"Issuer address {issuer_address} is not registered.")
    
    issuer_info = credential_registry_contract.functions.issuers(issuer_address).call()
    issuer_name = issuer_info[0]

    # 3. Construct the Verifiable Credential Payload (the "vc" claim)
    # This remains the same as before
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(days=365 * 10) # 10-year validity

    vc_payload = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "UniversityDegreeCredential"],
        "issuer": {
            "id": f"did:ethr:{issuer_address}", 
            "name": issuer_name
        },
        "issuanceDate": issued_at.isoformat() + "Z",
        "expirationDate": expires_at.isoformat() + "Z",
        "credentialSubject": {
            "id": f"did:example:{request.student_id}",
            "degree": {
                "type": "BachelorDegree",
                "name": request.degree_name,
                "major": request.major
            },
            "name": request.student_name
        }
    }

    # 4. Construct the main JWT Payload
    # This also remains the same
    jwt_payload = {
        "iss": f"did:ethr:{issuer_address}",
        "sub": f"did:example:{request.student_id}",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "vc": vc_payload
    }
    
    # 5. --- THIS IS THE NEW SIGNING LOGIC ---
    # Sign the JWT with the issuer's private key using eth_keys
    
    headers = {"alg": "ES256K", "typ": "JWT"}
    
    # Encode header and payload
    encoded_header = base64url_encode(json.dumps(headers).encode('utf-8'))
    encoded_payload = base64url_encode(json.dumps(jwt_payload).encode('utf-8'))

    # Create the signing input
    signing_input = encoded_header + b'.' + encoded_payload
    
    # Create a private key object from the raw hex key
    private_key = PrivateKey(bytes.fromhex(issuer_private_key_hex[2:]))
    
    # Sign the hash of the signing input
    message_hash = web3.keccak(signing_input)
    signature = private_key.sign_msg_hash(message_hash)
    
    # Encode the signature
    encoded_signature = base64url_encode(signature.to_bytes())

    # Combine all parts into the final JWS (JWT)
    signed_jwt = (encoded_header + b'.' + encoded_payload + b'.' + encoded_signature).decode('utf-8')
    
    return {"vc_jwt": signed_jwt}