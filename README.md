# Pharos Prometheus Exporter

A Python-based Prometheus exporter for [Pharos](https://pharosnetwork.xyz/) blockchain nodes.

This application queries a Pharos node via JSON-RPC to fetch status information (syncing, peer count, validator status) and exposes it as Prometheus-compatible metrics.

## Features

- **Sync Status**: Monitors if the node is currently syncing.
- **Block Height**: Tracks the current block number.
- **Peer Count**: Monitors the number of connected peers.
- **Validator Status**: Checks if a specific validator address is active in the current block's validator set.
- **Dockerized**: specific support for Python 3.14-slim.

## Metrics

The exporter exposes the following metrics at `/metrics`:

- `pharos_node_running` (Gauge): 1 if the node is reachable and responding to RPC calls, 0 otherwise.
- `pharos_node_syncing` (Gauge): 1 if the node is syncing, 0 if fully synced.
- `pharos_block_number` (Gauge): The current block number (height).
- `pharos_peer_count` (Gauge): The number of connected peers.
- `pharos_validator_working{validator_address="..."}` (Gauge): 1 if the specified validator address is found in the current validator set, 0 otherwise.

## Configuration

The application is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `RPC_URL` | **Required**. The JSON-RPC endpoint of the Pharos node (e.g., `https://your-pharos-node-rpc-url`). | `http://localhost:8545` |
| `POLL_INTERVAL` | Time in seconds between RPC polls. | `15` |
| `VALIDATOR_ADDRESS` | (Optional) The wallet address of the validator to monitor. | `None` |
| `PORT` | The port the exporter listens on (configured via uvicorn args or docker mapping). | `8000` |

## Running with Docker Compose (Recommended)

1.  Clone this repository.
2.  Edit `docker-compose.yml` to set your `RPC_URL` and `VALIDATOR_ADDRESS`.
    ```yaml
    environment:
      - RPC_URL=https://your-pharos-node-rpc-url
      - POLL_INTERVAL=15
      - VALIDATOR_ADDRESS=0xYourValidatorAddress
    ```

    > **Note:** With host networking, the service will bind directly to port 8000 on the host. Ensure this port is free. localhost (127.0.0.1) will work directly.

3.  Start the service:
    ```bash
    docker-compose up -d --build
    ```
4.  Metrics will be available at `http://localhost:8000/metrics`.

## Running with Docker

1.  Build the image:
    ```bash
    docker build -t pharos-prometheus-metrics .
    ```
2.  Run the container:
    ```bash
    docker run -d \
      --network host \
      -e RPC_URL="https://your-pharos-node-rpc-url" \
      -e VALIDATOR_ADDRESS="0x..." \
      --name pharos-prometheus-metrics \
      pharos-prometheus-metrics
    ```

## Development

To run locally without Docker:

1.  Install Python 3.14 or later.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    export RPC_URL="https://your-pharos-node-rpc-url"
    uvicorn main:app --reload --port 8000
    ```

## Prometheus Alerting Rules

Here is an example `alerts.yml` configuration for Prometheus to trigger alerts based on the metrics exposed by this exporter.

```yaml
groups:
  - name: pharos-node-alerts
    rules:
      - alert: PharosNodeDown
        expr: pharos_node_running == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Pharos node is down"
          description: "The Pharos node at {{ $labels.instance }} is not responding to RPC calls."

      - alert: PharosNodeSyncing
        expr: pharos_node_syncing == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pharos node is syncing"
          description: "The Pharos node at {{ $labels.instance }} has been syncing for more than 5 minutes."

      - alert: PharosValidatorNotWorking
        expr: pharos_validator_working == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Pharos validator is not working"
          description: "The validator {{ $labels.validator_address }} on {{ $labels.instance }} is not in the active validator set."
      
      - alert: PharosLowPeerCount
        expr: pharos_peer_count < 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pharos node has low peer count"
          description: "The Pharos node at {{ $labels.instance }} has only {{ $value }} peers."
```
