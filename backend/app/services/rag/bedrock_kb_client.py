import time
from typing import Any

from app.core.config import get_settings
from app.services.rag.retrieval_models import CareerRAGContext, RetrievedContextItem


class RAGConfigurationError(RuntimeError):
    pass


class RAGRetrievalError(RuntimeError):
    pass


class BedrockKnowledgeBaseRetriever:
    def __init__(
        self,
        *,
        knowledge_base_id: str | None = None,
        region_name: str | None = None,
        search_type: str | None = None,
        number_of_results: int | None = None,
        metrics_enabled: bool | None = None,
        metrics_namespace: str | None = None,
        bedrock_client: Any | None = None,
        cloudwatch_client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.knowledge_base_id = knowledge_base_id or settings.bedrock_kb_id
        self.region_name = region_name or settings.aws_region
        self.search_type = (search_type or settings.bedrock_kb_search_type or "HYBRID").upper()
        self.number_of_results = number_of_results or settings.bedrock_kb_number_of_results
        self.metrics_enabled = settings.rag_metrics_enabled if metrics_enabled is None else metrics_enabled
        self.metrics_namespace = metrics_namespace or settings.rag_metrics_namespace
        self.bedrock_client = bedrock_client
        self.cloudwatch_client = cloudwatch_client

    def retrieve(self, *, query: str, user_id: int | str, number_of_results: int | None = None) -> CareerRAGContext:
        if not self.knowledge_base_id:
            raise RAGConfigurationError("OFFERPATH_BEDROCK_KB_ID is required for Bedrock Knowledge Base retrieval.")

        user_id_value = str(user_id)
        result_count = number_of_results or self.number_of_results
        metadata_filter = {"equals": {"key": "user_id", "value": user_id_value}}
        request = {
            "knowledgeBaseId": self.knowledge_base_id,
            "retrievalQuery": {"text": query},
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {
                    "numberOfResults": result_count,
                    "overrideSearchType": self.search_type,
                    "filter": metadata_filter,
                }
            },
        }

        start = time.perf_counter()
        try:
            response = self._bedrock_client().retrieve(**request)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._put_metric("RetrievalErrors", 1, "Count", status="error", result_count=result_count)
            self._put_metric("RetrievalLatency", latency_ms, "Milliseconds", status="error", result_count=result_count)
            raise RAGRetrievalError(f"Bedrock Knowledge Base retrieve failed: {exc}") from exc

        latency_ms = (time.perf_counter() - start) * 1000
        items = _parse_retrieval_results(response.get("retrievalResults", []))
        self._put_metric("RetrievalLatency", latency_ms, "Milliseconds", status="success", result_count=result_count)
        self._put_metric("RetrievedItems", len(items), "Count", status="success", result_count=result_count)
        if not items:
            self._put_metric("EmptyRetrievals", 1, "Count", status="success", result_count=result_count)
        if items and items[0].score is not None:
            self._put_metric("TopResultScore", items[0].score, "None", status="success", result_count=result_count)
        return CareerRAGContext(
            query=query,
            user_id=user_id_value,
            items=items,
            metadata_filter=metadata_filter,
            search_type=self.search_type,
            number_of_results=result_count,
            latency_ms=latency_ms,
        )

    def _bedrock_client(self) -> Any:
        if self.bedrock_client is not None:
            return self.bedrock_client
        self.bedrock_client = _boto3_client("bedrock-agent-runtime", self.region_name)
        return self.bedrock_client

    def _cloudwatch_client(self) -> Any:
        if self.cloudwatch_client is not None:
            return self.cloudwatch_client
        self.cloudwatch_client = _boto3_client("cloudwatch", self.region_name)
        return self.cloudwatch_client

    def _put_metric(self, name: str, value: float, unit: str, *, status: str, result_count: int) -> None:
        if not self.metrics_enabled:
            return
        try:
            self._cloudwatch_client().put_metric_data(
                Namespace=self.metrics_namespace,
                MetricData=[
                    {
                        "MetricName": name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": [
                            {"Name": "KnowledgeBaseId", "Value": self.knowledge_base_id or "unknown"},
                            {"Name": "SearchType", "Value": self.search_type},
                            {"Name": "RequestedResults", "Value": str(result_count)},
                            {"Name": "Status", "Value": status},
                        ],
                    }
                ],
            )
        except Exception:
            return


def _boto3_client(service_name: str, region_name: str | None) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RAGConfigurationError("boto3 is required for Bedrock Knowledge Base retrieval.") from exc
    return boto3.client(service_name, region_name=region_name)


def _parse_retrieval_results(results: Any) -> list[RetrievedContextItem]:
    if not isinstance(results, list):
        return []
    items: list[RetrievedContextItem] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        content = result.get("content") if isinstance(result.get("content"), dict) else {}
        location = result.get("location") if isinstance(result.get("location"), dict) else {}
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        text = content.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        items.append(
            RetrievedContextItem(
                text=text.strip(),
                source_uri=_source_uri(location),
                score=result.get("score") if isinstance(result.get("score"), int | float) else None,
                metadata={str(key): str(value) for key, value in metadata.items()},
            )
        )
    return items


def _source_uri(location: dict[str, Any]) -> str | None:
    s3_location = location.get("s3Location")
    if isinstance(s3_location, dict) and isinstance(s3_location.get("uri"), str):
        return s3_location["uri"]
    web_location = location.get("webLocation")
    if isinstance(web_location, dict) and isinstance(web_location.get("url"), str):
        return web_location["url"]
    return None
