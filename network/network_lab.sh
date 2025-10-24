#!/usr/bin/env bash

# Network monitoring helper inspired by Lab2-net.pdf.
# Provides tcpdump capture, live nload monitoring, bandwidth charting, and
# optional firewall hardening that permits only HTTP/HTTPS inbound traffic.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
DEFAULT_DURATION=60
DEFAULT_INTERVAL=1

mkdir -p "${LOG_DIR}"

die() {
    echo "[!] $*" >&2
    exit 1
}

usage() {
    cat <<EOF
Usage:
  $(basename "$0") monitor [--interface IFACE] [--duration SECONDS] [--interval SECONDS]
  $(basename "$0") firewall
  $(basename "$0") help

Commands:
  monitor   Run tcpdump, launch nload for live monitoring, and chart bandwidth.
  firewall  Configure ufw to deny all inbound traffic except HTTP/HTTPS.
  help      Show this message.
EOF
}

require_cmd() {
    local cmd="$1"
    command -v "${cmd}" >/dev/null 2>&1 || die "Command '${cmd}' is required but not installed."
}

python_bin() {
    if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
        echo "${VIRTUAL_ENV}/bin/python"
    elif [[ -x "${ROOT_DIR}/env/bin/python" ]]; then
        echo "${ROOT_DIR}/env/bin/python"
    else
        echo "python3"
    fi
}

resolve_interface() {
    local default_iface
    default_iface="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
    if [[ -n "${default_iface}" ]]; then
        echo "${default_iface}"
        return
    fi
    ip -o link show | awk -F': ' '!/lo/ {print $2; exit}'
}

run_monitor() {
    local iface="" duration="${DEFAULT_DURATION}" interval="${DEFAULT_INTERVAL}"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --interface|-i)
                iface="$2"
                shift 2
                ;;
            --duration|-d)
                duration="$2"
                shift 2
                ;;
            --interval|-s)
                interval="$2"
                shift 2
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    require_cmd tcpdump
    require_cmd nload
    require_cmd timeout
    require_cmd script
    require_cmd ip

    local py_bin
    py_bin="$(python_bin)"

    "${py_bin}" - <<'PY' >/dev/null 2>&1 || die "matplotlib is required for charting. Install via pip."
import matplotlib  # noqa: F401
PY

    if [[ -z "${iface}" ]]; then
        iface="$(resolve_interface)"
    fi

    [[ -n "${iface}" ]] || die "Could not determine network interface. Specify via --interface."

    local ts
    ts="$(date -u +"%Y%m%d_%H%M%S")"
    local tcpdump_log="${LOG_DIR}/tcpdump_${iface}_${ts}.txt"
    local sampler_csv="${LOG_DIR}/nload_sample_${iface}_${ts}.csv"
    local chart_png="${LOG_DIR}/nload_chart_${iface}_${ts}.png"

    echo "[+] Using interface: ${iface}"
    echo "[+] Capture duration: ${duration}s (sample interval ${interval}s)"
    echo "[+] tcpdump log: ${tcpdump_log}"
    echo "[+] nload chart: ${chart_png}"

    echo "[1/4] Starting tcpdump capture..."
    # tcpdump requires elevated privileges. Expect timeout exit code 124.
    sudo timeout "${duration}" tcpdump -i "${iface}" -nn -tttt > "${tcpdump_log}" || true &
    local tcpdump_pid=$!

    echo "[2/4] Sampling bandwidth for charting..."
    "${py_bin}" "${SCRIPT_DIR}/sample_bandwidth.py" \
        --interface "${iface}" \
        --duration "${duration}" \
        --interval "${interval}" \
        --output "${sampler_csv}" \
        --plot "${chart_png}" &
    local sampler_pid=$!

    echo "[3/4] Launching nload for live monitoring..."
    # timeout may return 124 when it stops the process; ignore.
    timeout "${duration}" nload -t $((interval * 1000)) "${iface}" || true

    echo "[4/4] Finalizing..."
    wait "${sampler_pid}" || true
    wait "${tcpdump_pid}" || true

    echo "[✓] Monitoring complete."
    echo "    tcpdump -> ${tcpdump_log}"
    echo "    nload samples -> ${sampler_csv}"
    echo "    chart -> ${chart_png}"
}

configure_firewall() {
    require_cmd sudo
    require_cmd ufw

    echo "[+] Configuring ufw to block all inbound traffic except HTTP/HTTPS..."
    sudo ufw default deny incoming
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw deny proto tcp from any to any port 1:79 2>/dev/null || true
    sudo ufw deny proto tcp from any to any port 81:65535 2>/dev/null || true

    local status
    status="$(sudo ufw status | head -n 1)"
    if [[ "${status}" == "Status: inactive" ]]; then
        echo "[!] ufw is currently inactive. Run 'sudo ufw enable' if you wish to enforce rules."
    else
        echo "[✓] Updated ufw rules:"
        sudo ufw status numbered
    fi
}

main() {
    local cmd="${1:-help}"
    shift || true

    case "${cmd}" in
        monitor)
            run_monitor "$@"
            ;;
        firewall)
            configure_firewall
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            die "Unknown command: ${cmd}"
            ;;
    esac
}

main "$@"

