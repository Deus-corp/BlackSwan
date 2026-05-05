# Appendix AD – High-Performance RDMA Configuration and Monitoring Stack

## AD.1. Ubuntu 24.04 Setup for Mellanox ConnectX-5 (RoCE v2)
(details on MLNX_OFED installation, sysctl optimization, PFC/ECN, MTU 9000, IRQ Affinity)

## AD.2. RDMA Integration with vLLM and NCCL
(environment variables, Ray Head/Worker launch scripts, traffic verification)

## AD.3. Docker-compose for Isolated vLLM with Kata and RDMA
- runtime: kata, passthrough of `/dev/infiniband`, GPU VFIO, read-only weight mounts, `shm_size`, ulimits for NCCL.
> **Future work:** Specifics of GPU memory registration for RDMA inside micro‑VMs (IOMMU group requirements, kernel parameters `intel_iommu=on`, `vfio-pci`, `kata-runtime` VFIO configuration) will be detailed in a separate technical memorandum.

## AD.4. Prometheus + Grafana Monitoring Stack
- docker-compose services: dcgm-exporter (NVIDIA), node-exporter (with infiniband collector), Prometheus, Grafana.
- Example `prometheus.yml`.
- Key PromQL queries for RDMA and GPU.
- Alert configuration (temperature >85°C, RDMA port errors).
> **Future work:** Reference Grafana dashboard JSON models (GPU, RDMA, alerts) and the complete `prometheus.yml` with alerting rules will be preserved as artifacts and included in the next version of this appendix.

## AD.5. Integration with Arduino Watchdog
(monitoring metrics via Prometheus, automatic vLLM suspension on critical alerts)