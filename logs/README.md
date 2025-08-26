# Ingesting logs/app.jsonl into Loki with Promtail

This folder contains an example Promtail configuration to ingest the JSON-lines logs produced by the application (`logs/app.jsonl`) into Grafana Loki.

Quick steps

1. Install Loki and Promtail

   - You can run Loki locally using Docker Compose or the official Loki binary. For local testing, the Grafana Loki quickstart is handy.

2. Configure Promtail

   - Edit `promtail-config.yaml` if your app logs are stored outside this repository or you want different label settings. The default `__path__` scrapes `./logs/*.jsonl` relative to where promtail is started.

3. Start Promtail

   If you have the promtail binary:

   ```bash
   ./promtail --config.file=logs/promtail-config.yaml
   ```

   Or run promtail with Docker (example):

   ```bash
   docker run --rm -v $(pwd)/logs:/logs -v $(pwd)/logs/promtail-config.yaml:/etc/promtail/config.yaml grafana/promtail:latest --config.file=/etc/promtail/config.yaml
   ```

4. Start Loki (default listens on http://localhost:3100)

   - Use Docker Compose or the binary. Ensure the `clients.url` in `promtail-config.yaml` points to your Loki instance.

5. Query logs in Grafana

   - Add Loki as a data source in Grafana (URL: `http://localhost:3100`).
   - Example LogQL query to find slow plate detections:

   ```text
   {job="app", operation="run_plate_detection"} |= `duration_ms` | duration_ms > 500
   ```

   - Example to get errors:

   ```text
   {job="app", level="ERROR"}
   ```

Notes and tips

- The logger produces JSON-lines; Promtail's `json` pipeline stage extracts fields and the `labels` stage promotes chosen fields to Loki labels for efficient filtering.
- Keep labels small and select only fields you query frequently (e.g., operation, level, environment).
- If your timestamps are not parsed correctly, adjust the `timestamp` stage' `format` to match the `ts` format used by the logger (the logger uses RFC3339-like format with microseconds).
