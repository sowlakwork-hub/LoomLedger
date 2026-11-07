from google import genai

from app.config import get_settings


def generate_embedding(text: str) -> list[float]:
    """Generate a Gemini text embedding."""

    settings = get_settings()

    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    response = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config={
            "output_dimensionality": settings.embedding_dimensions
        },
    )

    return response.embeddings[0].values


if __name__ == "__main__":
    sample_text = (
        "KPR Mill reported revenue from operations "
        "in its annual financial statement."
    )

    vector = generate_embedding(sample_text)

    print("Embedding generated successfully!")
    print("Dimensions:", len(vector))
    print("First 5 values:", vector[:5])