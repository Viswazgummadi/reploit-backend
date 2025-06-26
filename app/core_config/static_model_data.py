# backend/app/core_config/static_model_data.py

# This list defines common models an admin might want to configure.
# It serves as a source for suggestions in the admin UI.
# The 'id' here is the provider's model identifier string.
# 'name' is a suggested display name.
# 'provider' helps categorize.
# 'default_api_key_placeholder' could suggest a common API key name pattern for the admin to use.

PREDEFINED_MODEL_SUGGESTIONS = [
    { 
        "id": "gemini-1.5-flash-latest", 
        "name": "Gemini 1.5 Flash",
        "provider": "Google",
        "notes": "Fast and versatile Google model.",
        "default_api_key_placeholder": "GEMINI_API_KEY" 
    },
    { 
        "id": "gemini-1.5-pro-latest", 
        "name": "Gemini 1.5 Pro", 
        "provider": "Google", 
        "notes": "Powerful, for complex tasks from Google.",
        "default_api_key_placeholder": "GEMINI_API_KEY"
    },
    {
        "id": "models/text-bison-001",
        "name": "PaLM 2 Text Bison (Legacy)",
        "provider": "Google", # Or "Google VertexAI" if you want to be more specific
        "notes": "Legacy text generation model from Google (Vertex AI).",
        "default_api_key_placeholder": "GEMINI_API_KEY" # Often same project/key
    },
    # --- Examples for other providers ---
    { 
        "id": "gpt-4o", 
        "name": "GPT-4 Omni", 
        "provider": "OpenAI", 
        "notes": "OpenAI's latest flagship model.",
        "default_api_key_placeholder": "OPENAI_API_KEY"
    },
    { 
        "id": "gpt-3.5-turbo", 
        "name": "GPT-3.5 Turbo", 
        "provider": "OpenAI", 
        "notes": "Fast and cost-effective model from OpenAI.",
        "default_api_key_placeholder": "OPENAI_API_KEY"
    },
    {
        "id": "claude-3-opus-20240229",
        "name": "Claude 3 Opus",
        "provider": "Anthropic",
        "notes": "Anthropic's most powerful model.",
        "default_api_key_placeholder": "ANTHROPIC_API_KEY"
    },
    {
        "id": "claude-3-sonnet-20240229",
        "name": "Claude 3 Sonnet",
        "provider": "Anthropic",
        "notes": "Balanced model from Anthropic.",
        "default_api_key_placeholder": "ANTHROPIC_API_KEY"
    },
    # --- Example for a local/custom model ---
    # {
    #     "id": "ollama/llama3:8b", 
    #     "name": "Llama 3 8B (Ollama)",
    #     "provider": "Ollama", 
    #     "notes": "Locally hosted Llama 3 8B model via Ollama.",
    #     "default_api_key_placeholder": None # Indicates no specific API key needed from DB
    # }
]

def get_predefined_model_suggestions():
    """Returns the list of predefined model suggestions."""
    return PREDEFINED_MODEL_SUGGESTIONS

def get_suggestion_by_id(model_id_string: str):
    """
    Finds a suggestion by its 'id' (provider's model ID string).
    Note: This might not be unique if different providers use the same ID string,
    so usually, you'd check provider as well if fetching a specific one.
    For a general list, this is fine.
    """
    for suggestion in PREDEFINED_MODEL_SUGGESTIONS:
        if suggestion["id"] == model_id_string:
            return suggestion
    return None