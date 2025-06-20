// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CredentialRegistry
 * @dev A simple registry to manage trusted issuers for the POC.
 */
contract CredentialRegistry {
    // The 'owner' is the account that deploys this contract and is the only one who can add new issuers.
    address public owner;

    // Data structure for each Issuer.
    struct Issuer {
        string name;
        bool isRegistered;
    }

    // Mapping to store Issuer data, using the Issuer's address as the key.
    mapping(address => Issuer) public issuers;

    // Event emitted when a new issuer is added, allowing other systems to listen for this change.
    event IssuerAdded(address indexed issuerAddress, string name);

    // Modifier to check if the caller of a function is the owner.
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    // The constructor runs only once when the contract is deployed.
    constructor() {
        // Set the deployer as the owner.
        owner = msg.sender;
    }

    /**
     * @dev Adds a new issuer to the registry. Can only be called by the owner.
     * @param _issuerAddress The address of the new issuer.
     * @param _name The name of the new issuer (e.g., "Chulalongkorn University").
     */
    function addIssuer(address _issuerAddress, string memory _name) public onlyOwner {
        require(!issuers[_issuerAddress].isRegistered, "Issuer already registered");
        issuers[_issuerAddress] = Issuer(_name, true);
        emit IssuerAdded(_issuerAddress, _name);
    }

    /**
     * @dev Checks if an issuer is registered and trusted.
     * @param _issuerAddress The address of the issuer to check.
     * @return bool True if the issuer is registered, false otherwise.
     */
    function isIssuerRegistered(address _issuerAddress) public view returns (bool) {
        return issuers[_issuerAddress].isRegistered;
    }
}