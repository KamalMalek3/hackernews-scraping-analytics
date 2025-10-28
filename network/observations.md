# Network Observation Log

Use this template to record manual measurements gathered during scraping runs.

- **Date & Time:** 
- **Interface Monitored:** (e.g., `eth0`)
- **Commands Executed:**
  - `ss -t -a | grep python` → Paste relevant sockets
  - `iftop -i ...` → Summarize inbound/outbound KB/s
  - `tcpdump -i any port 80 or port 443 -w network/scraper_trace.pcap` → Capture path
- **Firewall Actions:** Document any `ufw` rules applied and their effects.
- **Proxy Configuration:** Proxy endpoint, authentication, observed latency.
- **Observations:** Note anomalies, throttling behavior, or failures when ports are blocked.
