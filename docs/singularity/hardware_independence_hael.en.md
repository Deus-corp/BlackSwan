# Hardware Independence (HAEL)

**Purpose:** Describe the Hardware Abstraction and Execution Layer (HAEL), which ensures the system can run on various hardware architectures without external intervention.

---

## 1. Supported Architectures

- **Primary:** NVIDIA CUDA (via vLLM).
- **Secondary:** AMD ROCm, Intel oneAPI, Apple Metal, RISC‑V Vector.
- **Fallback:** CPU-only inference via llama.cpp.

## 2. Just‑in‑Time Kernel Compilation

HAEL uses a JIT compilation approach for GPU kernels. When migrating to a new architecture, the system automatically recompiles critical kernels into the target format.

## 3. PUF Binding

To prevent unauthorized copying, Core DNA is bound to the physical characteristics of the silicon (Physical Unclonable Function). When running on new hardware, proof of PUF ownership is required.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*