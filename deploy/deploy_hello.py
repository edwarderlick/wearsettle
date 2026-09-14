import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

def main():
    accounts = get_accounts()
    owner = accounts[0]
    factory = get_contract_factory("Hello")
    contract = factory.deploy(args=[], account=owner)
    print("HELLO_ADDRESS:", contract.address)

if __name__ == "__main__":
    main()
