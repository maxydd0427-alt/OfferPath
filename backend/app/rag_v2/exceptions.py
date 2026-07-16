class RAGV2Error(RuntimeError):
    pass


class RAGConfigurationError(RAGV2Error):
    pass


class RAGParsingError(RAGV2Error):
    pass


class RAGIngestionError(RAGV2Error):
    pass
