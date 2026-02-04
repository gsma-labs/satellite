"""Evaluation system data definitions.

This module contains data for the Open Telco Eval interface:
- EVAL_BOXES: The 3 main action boxes (Evals, Leaderboard, Submit)
- MODEL_BOXES: The 4 model category boxes (Lab APIs, Cloud APIs, etc.)
- get_benchmarks(): Dynamically loaded benchmarks from otelcos/evals registry
- PROVIDERS_BY_CATEGORY: Provider lists per category (from Inspect)
- MODEL_PROVIDERS: All providers (for backward compatibility)
- APP_INFO: Application metadata

Note: get_benchmarks is lazy-imported to avoid loading inspect-ai at module
import time, which can conflict with Textual's terminal driver.
"""


def get_benchmarks() -> list[dict]:
    """Get available benchmarks from the evals registry.

    Lazy import wrapper to avoid loading inspect-ai at module level.
    The actual import happens when this function is called, allowing
    Textual to set up its terminal driver first.
    """
    from satetoad.services.eval_registry import get_benchmarks as _get_benchmarks

    return _get_benchmarks()


# Main action boxes (top row)
EVAL_BOXES = [
    {
        "id": "evals",
        "name": "Evals",
        "description": "Select and run evaluations",
        "shortcut": "1",
    },
    {
        "id": "leaderboard",
        "name": "Leaderboard",
        "description": "View evaluation results and rankings",
        "shortcut": "2",
    },
    {
        "id": "submit",
        "name": "Submit",
        "description": "Submit results to the leaderboard",
        "shortcut": "3",
    },
]

# Model category boxes (below "Models" heading)
# No shortcut digits displayed - these are accessed via keys 4-7
MODEL_BOXES = [
    {
        "id": "lab-apis",
        "name": "Lab APIs",
        "description": "OpenAI, Anthropic, Google, Mistral",
        "shortcut": "",
    },
    {
        "id": "cloud-apis",
        "name": "Cloud APIs",
        "description": "AWS Bedrock, Azure AI, Google Vertex",
        "shortcut": "",
    },
    {
        "id": "open-hosted",
        "name": "Open (Hosted)",
        "description": "Groq, Together, Fireworks, OpenRouter",
        "shortcut": "",
    },
    {
        "id": "open-local",
        "name": "Open (Local)",
        "description": "Ollama, vLLM, HuggingFace local",
        "shortcut": "",
    },
]

# Provider categories following Inspect AI provider documentation
# https://inspect.aisi.org.uk/providers.html
PROVIDERS_BY_CATEGORY = {
    "lab-apis": [
        {"id": "openai", "name": "OpenAI", "model_prefix": "openai/", "env_var": "OPENAI_API_KEY"},
        {"id": "anthropic", "name": "Anthropic", "model_prefix": "anthropic/", "env_var": "ANTHROPIC_API_KEY"},
        {"id": "google", "name": "Google", "model_prefix": "google/", "env_var": "GOOGLE_API_KEY"},
        {"id": "mistral", "name": "Mistral", "model_prefix": "mistral/", "env_var": "MISTRAL_API_KEY"},
        {"id": "deepseek", "name": "DeepSeek", "model_prefix": "deepseek/", "env_var": "DEEPSEEK_API_KEY"},
        {"id": "grok", "name": "Grok (xAI)", "model_prefix": "grok/", "env_var": "XAI_API_KEY"},
        {"id": "perplexity", "name": "Perplexity", "model_prefix": "perplexity/", "env_var": "PERPLEXITY_API_KEY"},
    ],
    "cloud-apis": [
        {"id": "bedrock", "name": "AWS Bedrock", "model_prefix": "bedrock/", "env_var": "AWS_ACCESS_KEY_ID"},
        {"id": "azureai", "name": "Azure AI", "model_prefix": "azureai/", "env_var": "AZUREAI_API_KEY"},
        {"id": "vertex", "name": "Google Vertex", "model_prefix": "vertex/", "env_var": "GOOGLE_APPLICATION_CREDENTIALS"},
    ],
    "open-hosted": [
        {"id": "groq", "name": "Groq", "model_prefix": "groq/", "env_var": "GROQ_API_KEY"},
        {"id": "together", "name": "Together AI", "model_prefix": "together/", "env_var": "TOGETHER_API_KEY"},
        {"id": "fireworks", "name": "Fireworks", "model_prefix": "fireworks/", "env_var": "FIREWORKS_API_KEY"},
        {"id": "sambanova", "name": "SambaNova", "model_prefix": "sambanova/", "env_var": "SAMBANOVA_API_KEY"},
        {"id": "cloudflare", "name": "Cloudflare", "model_prefix": "cf/", "env_var": "CLOUDFLARE_API_TOKEN"},
        {"id": "openrouter", "name": "OpenRouter", "model_prefix": "openrouter/", "env_var": "OPENROUTER_API_KEY"},
        {"id": "hf-inference", "name": "HF Inference", "model_prefix": "hf-inference-providers/", "env_var": "HF_TOKEN"},
    ],
    "open-local": [
        {
            "id": "ollama",
            "name": "Ollama",
            "model_prefix": "ollama/",
            "credential_type": "base_url",
            "credential_label": "Base URL:",
            "credential_placeholder": "http://localhost:11434/v1",
            "credential_default": "http://localhost:11434/v1",
            "credential_required": False,
            "env_var": "OLLAMA_BASE_URL",
        },
        {
            "id": "vllm",
            "name": "vLLM",
            "model_prefix": "vllm/",
            "credential_type": "base_url",
            "credential_label": "Base URL:",
            "credential_placeholder": "http://localhost:8000/v1",
            "credential_default": "",
            "credential_required": False,
            "env_var": "VLLM_BASE_URL",
        },
        {
            "id": "sglang",
            "name": "SGLang",
            "model_prefix": "sglang/",
            "credential_type": "base_url",
            "credential_label": "Base URL:",
            "credential_placeholder": "http://localhost:30000/v1",
            "credential_default": "",
            "credential_required": False,
            "env_var": "SGLANG_BASE_URL",
        },
        {
            "id": "llama-cpp",
            "name": "Llama-cpp",
            "model_prefix": "llama-cpp-python/",
            "credential_type": "base_url",
            "credential_label": "Base URL:",
            "credential_placeholder": "http://localhost:8000/v1",
            "credential_default": "http://localhost:8000/v1",
            "credential_required": False,
            "env_var": "LLAMA_CPP_PYTHON_BASE_URL",
        },
        {
            "id": "hf-local",
            "name": "HuggingFace",
            "model_prefix": "hf/",
            "credential_type": "none",
            "credential_required": False,
            "env_var": "",
        },
        {
            "id": "transformerlens",
            "name": "TransformerLens",
            "model_prefix": "transformerlens/",
            "credential_type": "none",
            "credential_required": False,
            "env_var": "",
        },
        {
            "id": "nnterp",
            "name": "nnterp",
            "model_prefix": "nnterp/",
            "credential_type": "none",
            "credential_required": False,
            "env_var": "",
        },
    ],
}

# BENCHMARKS is now loaded dynamically from otelcos/evals registry
# Use get_benchmarks() function instead of this constant
__all__ = [
    "EVAL_BOXES",
    "MODEL_BOXES",
    "get_benchmarks",
    "PROVIDERS_BY_CATEGORY",
    "MODEL_PROVIDERS",
    "APP_INFO",
]

# Flattened list of all providers (for backward compatibility)
MODEL_PROVIDERS = [
    provider
    for providers in PROVIDERS_BY_CATEGORY.values()
    for provider in providers
]

APP_INFO = {
    "name": "Satellite",
    "emoji": "satellite",
    "version": "0.1.0",
    "tagline": "The central controller for all telecom evaluations.",
    "subtitle": "Developed by GSMA Open-Telco AI",
}
