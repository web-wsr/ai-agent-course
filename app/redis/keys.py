# 统一管理 key 命名

def chat_response_cache_key(question_hash: str) -> str:
    return f"chat: response: {question_hash}"

def rate_limit_key(user_id: str, api_name: str) -> str:
    return f"rate_limit: {api_name}: {user_id}"

def api_key_cache_key(api_key_hash: str) -> str:
    return f"api_key: {api_key_hash}"

def conversation_recent_messages_key(conversation_id: str) -> str:
    return f"conversation:{conversation_id}:recent_messages"


def agent_run_state_key(run_id: str) -> str:
    return f"agent:run:{run_id}:state"


def lock_key(resource: str, resource_id: str) -> str:
    return f"lock:{resource}:{resource_id}"

def rag_query_cache_key(query_hash: str, knowledge_base_id: str) -> str:
    return f"rag:query:{knowledge_base_id}:{query_hash}"

def verification_code_key(email: str) -> str:
    return f"verification_code:{email}"
