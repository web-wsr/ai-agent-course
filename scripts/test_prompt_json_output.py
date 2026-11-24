import json

from app.schemas.prompt import IntentClassificationResult


def main():
    raw_output = """
    {
      "intent": "unknown",
      "confidence": 0.92
    }
    """

    result = IntentClassificationResult.model_validate_json(raw_output)

    print(result.model_dump())


if __name__ == "__main__":
    main()
