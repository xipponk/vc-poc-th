# 🇹🇭 Thai Digital Credential - Proof of Concept (POC)

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: In Development](https://img.shields.io/badge/status-in%20development-orange.svg)
![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Framework: FastAPI](https://img.shields.io/badge/Framework-FastAPI-green.svg)

A Proof-of-Concept for a Verifiable Credential (VC) and Self-Sovereign Identity (SSI) infrastructure for the Thai education system.

## 🚀 Vision

This project aims to build a prototype demonstrating a modern, learner-centric approach to academic credentials. By leveraging W3C Verifiable Credentials and blockchain technology, we empower learners to own, manage, and share their educational achievements securely and privately. This POC serves as a technical demonstration to showcase the feasibility and benefits of this infrastructure for Thailand's higher education institutions.

---

## 🏛️ POC Architecture

This diagram illustrates the high-level architecture and workflow of the Proof of Concept, including the three main actors: the Issuer (University), the Holder (Learner), and the Verifier (Employer), all interacting via a private blockchain registry.

![POC Architecture Diagram](docs/diagrams/poc_architecture.png)


---

## ✨ Key Features

-   **Issuance:** Universities can issue tamper-evident digital credentials to learners.
-   **Holder Control:** Learners receive and store their credentials in a personal, standards-compliant digital wallet (e.g., Lissi Wallet).
-   **Verification:** Employers or other institutions (Relying Parties) can verify the authenticity and validity of a credential in real-time.
-   **Decentralized Trust:** A private blockchain (Ganache) is used to manage a registry of trusted issuers and credential statuses, removing single points of failure.

---

## 🛠️ Technology Stack

-   **Backend:** Python 3.10+, FastAPI
-   **Blockchain:** Solidity, Ganache, Web3.py
-   **Virtualization & Containers:** VirtualBox, Docker, Docker Compose
-   **Core Standards:** W3C Verifiable Credentials (VC), W3C Decentralized Identifiers (DIDs)
-   **Development Environment:** VS Code with Remote - SSH

---

## 🏁 Getting Started

### Prerequisites

-   Git
-   Python 3.10+
-   VirtualBox
-   An SSH Client (Built-in on Windows 11)
-   VS Code with the "Remote - SSH" extension by Microsoft.

### Installation & Running the POC

1.  **Clone the repository:**
    ```bash
    # git clone git@github.com:YourUsername/vc-poc-th.git
    cd vc-poc-th
    ```

2.  **Setup Virtual Machines:**
    -   Follow the internal guide to set up two Ubuntu Server 22.04 VMs using VirtualBox:
        -   `Issuer-VM`: Hosts the Issuer Service and Ganache node.
        -   `Verifier-VM`: Hosts the Verifier Service.
    -   Ensure both VMs have Guest Additions installed and are configured with two network adapters (Bridged and Host-Only).

3.  **Launch Services (Future Goal):**
    -   The services will be orchestrated using `docker-compose`.
    ```bash
    # (This will be implemented later)
    docker compose up --build
    ```

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
