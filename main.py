import os
import time
import requests
import threading
import json
from fastapi import FastAPI
from prometheus_client import Gauge

app = FastAPI()

# Configuration
RPC_URL = os.getenv("RPC_URL", "http://localhost:18100").strip('"\'')
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
VALIDATOR_ADDRESS = os.getenv("VALIDATOR_ADDRESS")
if VALIDATOR_ADDRESS:
    VALIDATOR_ADDRESS = VALIDATOR_ADDRESS.strip('"\'')

# Metrics
PHAROS_NODE_RUNNING = Gauge('pharos_node_running', 'Whether the Pharos node is running (reachable)')
PHAROS_NODE_SYNCING = Gauge('pharos_node_syncing', 'Whether the Pharos node is syncing (1=syncing, 0=synced)')
PHAROS_BLOCK_NUMBER = Gauge('pharos_block_number', 'Current block number')
PHAROS_VALIDATOR_WORKING = Gauge('pharos_validator_working', 'Whether the validator is currently working (in validator set)', ['validator_address'])
PHAROS_ADDRESS_BALANCE_WEI = Gauge('pharos_address_balance_wei', 'Balance of an address in Wei', ['address'])
PHAROS_ADDRESS_BALANCE_ETH = Gauge('pharos_address_balance_eth', 'Balance of an address in ETH', ['address'])

def make_rpc_request(method, params=None):
    if params is None:
        params = []
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    try:
        response = requests.post(RPC_URL, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling {method}: {e}")
        return None

def hex_to_int(hex_str: str) -> int:
    # handles "0x0" too
    return int(hex_str, 16)

def wei_to_eth(wei: int) -> float:
    return wei / 10**18

def update_metrics():
    while True:
        try:
            # Check availability (Block Number is a good proxy for "running")
            block_data = make_rpc_request("eth_blockNumber")
            
            if block_data and "result" in block_data:
                PHAROS_NODE_RUNNING.set(1)
                block_number = int(block_data["result"], 16)
                PHAROS_BLOCK_NUMBER.set(block_number)
                
                # Check syncing status
                sync_data = make_rpc_request("eth_syncing")
                if sync_data and sync_data.get("result"):
                    # result is an object if syncing, false if not
                    if isinstance(sync_data["result"], bool) and not sync_data["result"]:
                         PHAROS_NODE_SYNCING.set(0)
                    else:
                        PHAROS_NODE_SYNCING.set(1)
                else:
                    # Fallback or error assume syncing or not? standard is false if false
                    PHAROS_NODE_SYNCING.set(0)

                # address balance metric
                if VALIDATOR_ADDRESS:
                    bal_data = make_rpc_request("eth_getBalance", [VALIDATOR_ADDRESS, "latest"])
                    if bal_data and "result" in bal_data and bal_data["result"]:
                        wei = hex_to_int(bal_data["result"])
                        PHAROS_ADDRESS_BALANCE_WEI.labels(address=VALIDATOR_ADDRESS).set(float(wei))
                        PHAROS_ADDRESS_BALANCE_ETH.labels(address=VALIDATOR_ADDRESS).set(wei_to_eth(wei))
                    else:
                        # if RPC fails, set to NaN-like behavior, prometheus client doesn't do NaN weel consistently
                        # will just set 0
                        PHAROS_ADDRESS_BALANCE_WEI.labels(address=VALIDATOR_ADDRESS).set(0)
                        PHAROS_ADDRESS_BALANCE_ETH.labels(address=VALIDATOR_ADDRESS).set(0)

                # Check validator status if address provided
                if VALIDATOR_ADDRESS:
                    # Using debug_getValidatorInfo as found in docs
                    # We check if our address is in the list
                    val_data = make_rpc_request("debug_getValidatorInfo", [hex(block_number)])
                    
                    is_working = 0
                    if val_data and "result" in val_data:
                        # result: [block_num, [validator_info_objects...]]
                        # The docs showed: String - Block number, Array - List of validator info
                        # We need to parse the array. Assuming the array contains objects with an address field
                        # or similar. Since we don't have the exact structure of the object from the snippet,
                        # we will look for string match of the address in the raw string dump of the result
                        # or iterate assuming dictionary if we can guess.
                        # Note: The docs showed "Array - List of validator info".
                        # Let's assume it's a list of dicts with 'address' or similar, OR just use string search primarily.
                        
                        # Safer approach given limited docs: Check if address string is inside the result dump
                        # Case-insensitive check
                        import json
                        result_str = json.dumps(val_data["result"]).lower()
                        if VALIDATOR_ADDRESS.lower() in result_str:
                            is_working = 1
                    
                    PHAROS_VALIDATOR_WORKING.labels(validator_address=VALIDATOR_ADDRESS).set(is_working)

            else:
                PHAROS_NODE_RUNNING.set(0)
                
        except Exception as e:
            print(f"Error in metrics loop: {e}")
            PHAROS_NODE_RUNNING.set(0)
        
        time.sleep(POLL_INTERVAL)

# Start background thread
metrics_thread = threading.Thread(target=update_metrics, daemon=True)
metrics_thread.start()

# Metrics Endpoint
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
