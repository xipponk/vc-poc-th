import json
from web3 import Web3
from solcx import compile_source, install_solc
import os

def deploy_contract():
    # 1. Install and select the Solidity Compiler version.
    solc_version = '0.8.20'
    print(f"Checking/Installing solc version {solc_version}...")
    install_solc(solc_version)

    # 2. Read the Solidity source code from the file.
    contract_path = os.path.join(os.path.dirname(__file__), '..', 'contracts', 'CredentialRegistry.sol')
    with open(contract_path, 'r') as file:
        contract_source_code = file.read()
        
    print("Compiling contract...")
    # 3. Compile the code.
    compiled_sol = compile_source(
        contract_source_code,
        output_values=['abi', 'bin'],
        solc_version=solc_version
    )
    contract_id, contract_interface = compiled_sol.popitem()
    bytecode = contract_interface['bin']
    abi = contract_interface['abi']
    
    # 4. Connect to Ganache.
    ganache_url = "http://127.0.0.1:8545"
    web3 = Web3(Web3.HTTPProvider(ganache_url))

    if not web3.is_connected():
        print("Failed to connect to Ganache!")
        return

    print(f"Connected to Ganache. Chain ID: {web3.eth.chain_id}")
    
    # 5. Prepare for deployment.
    # Use the first account from Ganache as the deployer (Owner).
    deployer_account = web3.eth.accounts[0]
    web3.eth.default_account = deployer_account
    print(f"Using deployer account: {deployer_account}")
    
    # Create a Contract object.
    CredentialRegistry = web3.eth.contract(abi=abi, bytecode=bytecode)
    
    # 6. Send the transaction to deploy the Contract.
    print("Deploying contract...")
    tx_hash = CredentialRegistry.constructor().transact()
    
    # Wait for the transaction to be mined and confirmed.
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    
    contract_address = tx_receipt.contractAddress
    print(f"✅ Contract Deployed Successfully!")
    print(f"   - Contract Address: {contract_address}")
    
    # 7. Save the ABI and Address for later use.
    # The FastAPI service will use this file to interact with the contract.
    artifact = {
        "abi": abi,
        "address": contract_address
    }
    artifact_path = os.path.join(os.path.dirname(__file__), '..', '..', 'issuer-service', 'app', 'contract_artifact.json')
    with open(artifact_path, 'w') as f:
        json.dump(artifact, f, indent=2)
        
    print(f"   - Artifact saved to: {artifact_path}")

if __name__ == "__main__":
    deploy_contract()