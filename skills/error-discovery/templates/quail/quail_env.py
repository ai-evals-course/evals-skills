"""Modal image for Quail. Installs quail-engine from GitHub main with uv (PyPI 0.1.0 is older).

ask_app.py mounts two Modal volumes that cache model weights and compiled kernels between runs.
"""
import modal

UV_VERSION = "0.12.13"
CACHE_ENV = {
    "QUAIL_CACHE_DIR": "/root/.cache/kernels", "FLASHINFER_WORKSPACE_BASE": "/root/.cache/kernels",
    "VLLM_CACHE_ROOT": "/root/.cache/kernels/vllm", "VLLM_LOGGING_LEVEL": "WARNING",
    "VLLM_USE_FLASHINFER_SAMPLER": "0", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    "HF_HUB_ENABLE_HF_TRANSFER": "1", "DG_CACHE_DIR": "/root/.cache/kernels/deep_gemm",
    "DG_JIT_CACHE_DIR": "/root/.cache/kernels/deep_gemm", "TRITON_CACHE_DIR": "/root/.cache/kernels/triton",
    "TORCHINDUCTOR_CACHE_DIR": "/root/.cache/kernels/torchinductor",
    "FLASH_ATTENTION_CUTE_DSL_CACHE_ENABLED": "1",
    "FLASH_ATTENTION_CUTE_DSL_CACHE_DIR": "/root/.cache/kernels/flash_attention_cute",
}


def quail_image():
    return (modal.Image.from_registry("nvidia/cuda:13.0.1-devel-ubuntu24.04", add_python="3.12")
            .apt_install("git").env(CACHE_ENV)
            # PyPI 0.1.0 (Sep 24) rejects plain WHERE predicates; main supports them
            .uv_pip_install("quail-engine @ git+https://github.com/fsdatalab/quail.git@main", "pyarrow",
                            uv_version=UV_VERSION)
            .add_local_python_source("quail_env"))
