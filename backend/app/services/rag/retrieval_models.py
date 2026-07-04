from pydantic import BaseModel, Field


class RetrievedContextItem(BaseModel):
    text: str
    source_uri: str | None = None
    score: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class CareerRAGContext(BaseModel):
    query: str
    user_id: str
    items: list[RetrievedContextItem] = Field(default_factory=list)
    metadata_filter: dict[str, object]
    search_type: str = "HYBRID"
    number_of_results: int = 5
    latency_ms: float | None = None
    enabled: bool = True
    error: str | None = None

    @property
    def used(self) -> bool:
        return bool(self.items)
