import json
import os
import io
import base64
import uuid
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web3 import Web3
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jws
from eth_keys.main import PrivateKey
from jose.utils import base64url_encode
import qrcode

# --- Configuration ---
GANACHE_URL = "http://127.0.0.1:8545"
CREDENTIAL_LOG_FILE = "issued_credentials_log.json"

# --- Global Variables & App Setup ---
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))
templates = Jinja2Templates(directory="app/templates")
app = FastAPI()

# In-memory "databases"
issued_credentials_db = {}
credential_offers = {}

# --- Helper function to load contract ---
def load_contract_and_keys():
    """Loads contract artifact and sets up global variables."""
    global credential_registry_contract, GANACHE_PRIVATE_KEYS
    try:
        artifact_path = os.path.join(os.path.dirname(__file__), 'contract_artifact.json')
        with open(artifact_path, 'r') as f:
            contract_artifact = json.load(f)
        
        credential_registry_contract = web3.eth.contract(
            address=contract_artifact['address'],
            abi=contract_artifact['abi']
        )
        web3.eth.default_account = web3.eth.accounts[0]
        
        GANACHE_PRIVATE_KEYS = [
            "0x08c0ef735d7e1db5a837525d88cc88798e69270044587c79a9dbf5f427d6fa1e",
            "0x4553a1f8b17d1e527df3a4e75838a363b406713118c3bb52cb2ff5bac2694099",
            "0x4d89334fd6bc5afe06992419121640da811c30e190c2dcf4e5f33441cd0a1921",
            "0x3c7742e87de76a2a56bd5947bbc51c3346c510ae9cef8df76313e9a71a3fd691",
        ]
        print("✅ Contract and keys loaded successfully.")
        return True
    except Exception as e:
        print(f"🔴 ERROR loading contract: {e}")
        return False

# --- Startup Event ---
@app.on_event("startup")
def startup_event():
    global issued_credentials_db
    if load_contract_and_keys():
        if os.path.exists(CREDENTIAL_LOG_FILE):
            with open(CREDENTIAL_LOG_FILE, 'r') as f:
                try:
                    issued_credentials_db = json.load(f)
                    print(f"✅ Loaded {len(issued_credentials_db)} credentials from log file.")
                except json.JSONDecodeError:
                    print(f"⚠️ {CREDENTIAL_LOG_FILE} is empty or corrupted.")
                    issued_credentials_db = {}
        else:
            print(f"ℹ️ {CREDENTIAL_LOG_FILE} not found. Starting fresh.")
    else:
        print("🔴 FATAL: Could not load contract. Some endpoints may not work.")

# --- Pydantic Models ---
class IssuerRegistration(BaseModel):
    issuer_address: str
    issuer_name: str

# --- API Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    registered_issuers = []
    all_potential_accounts = web3.eth.accounts[:10]
    for index, account in enumerate(all_potential_accounts):
        is_registered = credential_registry_contract.functions.isIssuerRegistered(account).call()
        if is_registered:
            issuer_info = credential_registry_contract.functions.issuers(account).call()
            registered_issuers.append({
                "address": account, "name": issuer_info[0], "account_index": index
            })
    return templates.TemplateResponse("dashboard.html", {"request": request, "registered_issuers": registered_issuers})

@app.post("/credentials/issue")
async def issue_credential_and_redirect(
    issuer_account_index: int = Form(...), student_id: str = Form(...),
    student_name: str = Form(...), degree_name: str = Form(...),
    degree_type: str = Form(...), 
    major: str = Form(...)
):
    try:
        issuer_address = web3.eth.accounts[issuer_account_index]
        issuer_private_key_hex = GANACHE_PRIVATE_KEYS[issuer_account_index]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid issuer_account_index")
    
    is_registered = credential_registry_contract.functions.isIssuerRegistered(issuer_address).call()
    if not is_registered:
        raise HTTPException(status_code=400, detail=f"Issuer address {issuer_address} is not registered.")
    
    issuer_info = credential_registry_contract.functions.issuers(issuer_address).call()
    issuer_name = issuer_info[0]

    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(days=365 * 10)
    
    vc_payload = { "@context": ["https://www.w3.org/2018/credentials/v1"], "type": ["VerifiableCredential", "UniversityDegreeCredential"], "issuer": {"id": f"did:ethr:{issuer_address}", "name": issuer_name}, "issuanceDate": issued_at.isoformat() + "Z", "expirationDate": expires_at.isoformat() + "Z", "credentialSubject": { "id": f"did:example:{student_id}", "degree": {"type": degree_type, "name": degree_name, "major": major}, "name": student_name } }
    jwt_payload = { "iss": f"did:ethr:{issuer_address}", "sub": f"did:example:{student_id}", "iat": int(issued_at.timestamp()), "exp": int(expires_at.timestamp()), "vc": vc_payload }
    
    headers = {"alg": "ES256K", "typ": "JWT"}
    private_key = PrivateKey(bytes.fromhex(issuer_private_key_hex[2:]))
    signing_input = base64url_encode(json.dumps(headers).encode('utf-8')) + b'.' + base64url_encode(json.dumps(jwt_payload).encode('utf-8'))
    message_hash = web3.keccak(signing_input)
    signature = private_key.sign_msg_hash(message_hash)
    encoded_signature = base64url_encode(signature.to_bytes())
    signed_jwt = (signing_input + b'.' + encoded_signature).decode('utf-8')

    credential_id = str(uuid.uuid4())
    issued_credentials_db[credential_id] = { "jwt": signed_jwt, "student_name": student_name, "degree_name": degree_name, "issuer_name": issuer_name }
    
    with open(CREDENTIAL_LOG_FILE, 'w') as f:
        json.dump(issued_credentials_db, f, indent=2)
    
    return RedirectResponse(url=f"/credentials/jwt/{credential_id}", status_code=303)


@app.get("/credentials/issued", response_class=HTMLResponse)
async def list_issued_credentials(request: Request):
    """Displays a dashboard of all persistently saved credentials."""
    # --- NEW LOGIC: Read directly from the file every time ---
    local_issued_db = {}
    if os.path.exists(CREDENTIAL_LOG_FILE):
        with open(CREDENTIAL_LOG_FILE, 'r') as f:
            try:
                local_issued_db = json.load(f)
            except json.JSONDecodeError:
                pass # File is empty, do nothing
                
    return templates.TemplateResponse("issued_list.html", {"request": request, "credentials": local_issued_db})

@app.get("/credentials/jwt/{credential_id}", response_class=HTMLResponse)
async def get_credential_jwt_page(request: Request, credential_id: str):
    """
    This endpoint retrieves an issued credential by its ID from the log file
    and displays the raw JWT on a simple HTML page for copying.
    """
    # Read the database from the file on every request to ensure fresh data
    local_issued_db = {}
    if os.path.exists(CREDENTIAL_LOG_FILE):
        with open(CREDENTIAL_LOG_FILE, 'r') as f:
            try:
                local_issued_db = json.load(f)
            except json.JSONDecodeError:
                pass # File is empty

    credential_data = local_issued_db.get(credential_id)
    if not credential_data:
        raise HTTPException(status_code=404, detail=f"Credential ID '{credential_id}' not found in log file.")

    vc_jwt = credential_data["jwt"]
    return templates.TemplateResponse("copy_credential.html", {"request": request, "vc_jwt": vc_jwt})

@app.get("/credentials/qr/{credential_id}", response_class=HTMLResponse)
async def get_credential_qr(request: Request, credential_id: str):
    credential_data = issued_credentials_db.get(credential_id)
    if not credential_data:
        raise HTTPException(status_code=404, detail="Credential not found.")
    
    signed_jwt = credential_data["jwt"]
    offer_id = str(uuid.uuid4())
    credential_offers[offer_id] = signed_jwt
    
    # IMPORTANT: Update this IP to your VM's Bridged Adapter IP
    credential_offer_uri = f"http://192.168.56.104:8000/credentials/offer/{offer_id}"
    openid_offer_url = f"openid-credential-offer://?credential_offer_uri={credential_offer_uri}"
    
    qr_img = qrcode.make(openid_offer_url)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return templates.TemplateResponse("display_qr.html", {"request": request, "qr_image_base64": img_str})


@app.get("/credentials/offer/{offer_id}", response_class=JSONResponse)
async def get_credential_offer(offer_id: str):
    vc_jwt = credential_offers.get(offer_id)
    if not vc_jwt:
        raise HTTPException(status_code=404, detail="Offer not found or already claimed.")
    del credential_offers[offer_id]
    
    credential_offer_payload = {
        "credential_issuer": "https://poc.my-university.com",
        "credentials": [ { "format": "jwt_vc_json", "credential": vc_jwt, "types": ["VerifiableCredential", "UniversityDegreeCredential"] } ]
    }
    return JSONResponse(content=credential_offer_payload)


# ===================================================================
# ===               UTILITY & DEBUGGING ENDPOINTS                 ===
# ===================================================================

class IssuerRegistration(BaseModel):
    issuer_address: str
    issuer_name: str

@app.post("/register-issuer", tags=["Utility"])
def register_issuer(issuer_data: IssuerRegistration):
    """Utility endpoint to register new issuers on the blockchain."""
    try:
        tx_hash = credential_registry_contract.functions.addIssuer(
            issuer_data.issuer_address,
            issuer_data.issuer_name
        ).transact()
        web3.eth.wait_for_transaction_receipt(tx_hash)
        return {"status": "success", "message": f"Issuer '{issuer_data.issuer_name}' registered."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/blockchain-info", tags=["Utility"])
def get_blockchain_info():
    """Utility endpoint to check blockchain connection and status."""
    if web3.is_connected():
        return {
            "status": "Connected", "chain_id": web3.eth.chain_id,
            "latest_block_number": web3.eth.block_number,
            "contract_address": credential_registry_contract.address,
            "contract_owner": credential_registry_contract.functions.owner().call(),
            "ganache_accounts": web3.eth.accounts
        }
    else:
        return {"status": "Not Connected"}