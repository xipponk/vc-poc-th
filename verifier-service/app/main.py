import json
import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from web3 import Web3
from jose import jwt, jws
from eth_keys.main import PublicKey, Signature
import base64

# --- Configuration ---
# IMPORTANT: This must be the IP address of VM1 where Ganache is running.
# Use the Host-Only adapter IP for inter-VM communication.
GANACHE_URL = "http://10.4.155.79:8545" 
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

# Load the contract artifact (ABI and Address) copied from VM1
try:
    artifact_path = os.path.join(os.path.dirname(__file__), 'contract_artifact.json')
    with open(artifact_path, 'r') as f:
        contract_artifact = json.load(f)
    contract_address = contract_artifact['address']
    contract_abi = contract_artifact['abi']
    credential_registry_contract = web3.eth.contract(
        address=contract_address,
        abi=contract_abi
    )
    print("✅ Successfully connected to Blockchain and loaded contract.")
except FileNotFoundError:
    print("🔴 ERROR: contract_artifact.json not found. Please copy it from the issuer-service.")
    credential_registry_contract = None
except Exception as e:
    print(f"🔴 ERROR: Could not connect to blockchain or load contract: {e}")
    credential_registry_contract = None

app = FastAPI()

# --- Pydantic Model for incoming request ---
class VerificationRequest(BaseModel):
    vc_jwt: str

# --- Verification Logic ---
def verify_vc_jwt(vc_jwt: str):
    # 1. Decode the JWT without verifying the signature yet to read the claims
    try:
        unverified_claims = jwt.get_unverified_claims(vc_jwt)
        unverified_headers = jwt.get_unverified_headers(vc_jwt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JWT format: {e}")

    # 2. Extract Issuer's Address from the 'iss' claim
    issuer_did = unverified_claims.get('iss')
    if not issuer_did or not issuer_did.startswith('did:ethr:'):
        raise HTTPException(status_code=400, detail="Missing or invalid 'iss' (issuer) claim in JWT.")

    issuer_address = web3.to_checksum_address(issuer_did.replace('did:ethr:', ''))

    # 3. --- THIS IS THE CORRECTED CRYPTOGRAPHIC VERIFICATION LOGIC ---
    try:
        # Reconstruct the part of the JWT that was signed
        message, encoded_signature = vc_jwt.rsplit('.', 1)
        signing_input = message.encode('utf-8')

        # Create a message hash
        message_hash = web3.keccak(signing_input)

        # Create a Signature object from the raw signature bytes
        # The '==' is needed to pad the base64 string correctly for decoding
        signature_bytes = base64.urlsafe_b64decode(encoded_signature + '==')
        signature_obj = Signature(signature_bytes)

        # Recover the public key FROM the signature object itself
        recovered_public_key = signature_obj.recover_public_key_from_msg_hash(message_hash)

        # Get the address from the recovered public key
        recovered_address = recovered_public_key.to_checksum_address()

        # Check if the address recovered from the signature matches the issuer's address
        if recovered_address != issuer_address:
            raise ValueError("Signature is invalid. Recovered address does not match issuer.")

    except Exception as e:
        # Using ValueError for specific signature failure, but catching broader exceptions too
        raise HTTPException(status_code=400, detail=f"Cryptographic verification failed: {e}")

    # 4. Blockchain Registry Verification
    if not credential_registry_contract:
        raise HTTPException(status_code=500, detail="Verifier is not connected to the blockchain registry.")

    is_registered = credential_registry_contract.functions.isIssuerRegistered(issuer_address).call()
    if not is_registered:
        raise HTTPException(status_code=400, detail=f"Issuer {issuer_address} is not registered or not trusted in the blockchain registry.")

    # 5. If all checks pass, return the verified claims
    return {"valid": True, "claims": unverified_claims}

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Hello from Verifier Service!"}

@app.post("/verify")
def verify_credential(verification_request: VerificationRequest):
    result = verify_vc_jwt(verification_request.vc_jwt)
    return result