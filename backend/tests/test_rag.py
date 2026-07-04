from app.services.rag import BedrockKnowledgeBaseRetriever, RAGConfigurationError, build_rag_tuning_report
from app.services.rag.retrieval_models import CareerRAGContext, RetrievedContextItem


def test_bedrock_retriever_uses_user_filter_hybrid_search_and_metrics() -> None:
    bedrock_client = FakeBedrockAgentRuntimeClient()
    cloudwatch_client = FakeCloudWatchClient()
    retriever = BedrockKnowledgeBaseRetriever(
        knowledge_base_id="kb-123",
        region_name="us-east-1",
        bedrock_client=bedrock_client,
        cloudwatch_client=cloudwatch_client,
        metrics_enabled=True,
    )

    context = retriever.retrieve(query="AI SRE AWS Kubernetes", user_id=42)

    request = bedrock_client.requests[0]
    vector_config = request["retrievalConfiguration"]["vectorSearchConfiguration"]
    assert request["knowledgeBaseId"] == "kb-123"
    assert vector_config["overrideSearchType"] == "HYBRID"
    assert vector_config["numberOfResults"] == 5
    assert vector_config["filter"] == {"equals": {"key": "user_id", "value": "42"}}
    assert context.items[0].text == "AWS incident response portfolio project note"
    assert context.items[0].source_uri == "s3://offerpath-kb/users/42/note.md"
    assert context.metadata_filter == {"equals": {"key": "user_id", "value": "42"}}
    metric_names = [metric["MetricName"] for call in cloudwatch_client.calls for metric in call["MetricData"]]
    assert "RetrievalLatency" in metric_names
    assert "RetrievedItems" in metric_names
    latency_metric = next(
        metric
        for call in cloudwatch_client.calls
        for metric in call["MetricData"]
        if metric["MetricName"] == "RetrievalLatency"
    )
    assert {"Name": "SearchType", "Value": "HYBRID"} in latency_metric["Dimensions"]
    assert {"Name": "RequestedResults", "Value": "5"} in latency_metric["Dimensions"]
    assert {"Name": "Status", "Value": "success"} in latency_metric["Dimensions"]


def test_bedrock_retriever_requires_knowledge_base_id() -> None:
    retriever = BedrockKnowledgeBaseRetriever(knowledge_base_id=None, bedrock_client=FakeBedrockAgentRuntimeClient())

    try:
        retriever.retrieve(query="AI SRE", user_id=1)
    except RAGConfigurationError as exc:
        assert "OFFERPATH_BEDROCK_KB_ID" in str(exc)
    else:
        raise AssertionError("Expected missing Knowledge Base id to fail clearly")


def test_bedrock_retriever_records_empty_retrieval_metric() -> None:
    bedrock_client = FakeEmptyBedrockAgentRuntimeClient()
    cloudwatch_client = FakeCloudWatchClient()
    retriever = BedrockKnowledgeBaseRetriever(
        knowledge_base_id="kb-123",
        bedrock_client=bedrock_client,
        cloudwatch_client=cloudwatch_client,
        metrics_enabled=True,
    )

    context = retriever.retrieve(query="rare skill", user_id=42)

    assert context.items == []
    metric_names = [metric["MetricName"] for call in cloudwatch_client.calls for metric in call["MetricData"]]
    assert "EmptyRetrievals" in metric_names


def test_rag_tuning_report_flags_high_latency_and_empty_retrieval() -> None:
    context = CareerRAGContext(
        query="AI SRE",
        user_id="42",
        items=[],
        metadata_filter={"equals": {"key": "user_id", "value": "42"}},
        search_type="HYBRID",
        latency_ms=900,
    )

    report = build_rag_tuning_report(context, latency_target_ms=500)

    codes = [recommendation.code for recommendation in report.recommendations]
    assert "high_latency" in codes
    assert "empty_retrieval" in codes
    assert report.needs_attention is True


def test_rag_tuning_report_flags_filter_and_search_type_problems() -> None:
    context = CareerRAGContext(
        query="AI SRE",
        user_id="42",
        items=[RetrievedContextItem(text="Some context", score=0.2)],
        metadata_filter={},
        search_type="SEMANTIC",
        latency_ms=120,
    )

    report = build_rag_tuning_report(context)

    codes = [recommendation.code for recommendation in report.recommendations]
    assert "metadata_filter_mismatch" in codes
    assert "enable_hybrid_search" in codes
    assert "low_similarity" in codes


class FakeBedrockAgentRuntimeClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def retrieve(self, **kwargs):
        self.requests.append(kwargs)
        return {
            "retrievalResults": [
                {
                    "content": {"text": "AWS incident response portfolio project note"},
                    "location": {"s3Location": {"uri": "s3://offerpath-kb/users/42/note.md"}},
                    "metadata": {"user_id": "42", "document_type": "learning_note"},
                    "score": 0.91,
                }
            ]
        }


class FakeEmptyBedrockAgentRuntimeClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def retrieve(self, **kwargs):
        self.requests.append(kwargs)
        return {"retrievalResults": []}


class FakeCloudWatchClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_metric_data(self, **kwargs):
        self.calls.append(kwargs)
