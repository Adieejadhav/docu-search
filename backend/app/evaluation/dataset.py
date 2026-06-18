"""
File: backend/app/evaluation/dataset.py
Purpose: Provides fixed RAG evaluation cases for the Aquila fixture corpus.
"""

from __future__ import annotations

from app.evaluation.schema import EvaluationCase


BUILTIN_EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        id="satellite-mode-exception",
        question="Which policy mentions the 14-day satellite-mode exception?",
        expected_answer_terms=["P-004", "Password rotation exception", "14 days"],
        expected_context_terms=["P-004", "14 days", "satellite mode"],
        expected_source_files=[
            "02_aquila_product_knowledge_base.md",
            "03_aquila_security_runbook.markdown",
            "09_aquila_nested_corpus.json",
        ],
        tags=["policy", "exact-value", "source"],
    ),
    EvaluationCase(
        id="model-assisted-triage-owner",
        question="Which team owns model-assisted triage?",
        expected_answer_terms=["Service Desk Manager"],
        expected_context_terms=["P-005", "Model-assisted triage", "Service Desk Manager"],
        expected_source_files=[
            "02_aquila_product_knowledge_base.md",
            "05_aquila_docx_procedure_fixture.docx",
            "09_aquila_nested_corpus.json",
        ],
        tags=["policy", "owner"],
    ),
    EvaluationCase(
        id="policy-evidence-required",
        question="What evidence is required for policy verification?",
        expected_answer_terms=["ticket", "approval note", "timestamp"],
        expected_context_terms=["Evidence Required", "ticket", "approval note", "timestamp"],
        expected_source_files=[
            "02_aquila_product_knowledge_base.md",
            "05_aquila_docx_procedure_fixture.docx",
        ],
        tags=["table", "policy", "exact-values"],
    ),
    EvaluationCase(
        id="hourly-metrics-retention",
        question="How long are hourly aggregated metrics retained?",
        expected_answer_terms=["7 years"],
        expected_context_terms=["P-002", "Aggregated hourly metrics", "7 years"],
        expected_source_files=[
            "02_aquila_product_knowledge_base.md",
            "04_aquila_pdf_audit_report.pdf",
            "05_aquila_docx_procedure_fixture.docx",
        ],
        tags=["policy", "retention", "exact-value"],
    ),
    EvaluationCase(
        id="ai-triage-dispatch-rule",
        question="Can AI triage directly assign a crew?",
        expected_answer_terms=["No", "Human dispatchers", "safety classification"],
        expected_context_terms=["AI triage suggestions are advisory", "Human dispatchers"],
        expected_source_files=[
            "01_aquila_operations_plain_text.txt",
            "02_aquila_product_knowledge_base.md",
            "05_aquila_docx_procedure_fixture.docx",
        ],
        tags=["policy", "safety", "negative-answer"],
    ),
    EvaluationCase(
        id="gateway-certificate-frequency",
        question="How often is the gateway certificate check required?",
        expected_answer_terms=["every connection"],
        expected_context_terms=["Gateway certificate check", "every connection"],
        expected_source_files=["03_aquila_security_runbook.markdown"],
        tags=["security", "table", "exact-value"],
    ),
    EvaluationCase(
        id="asset-alias-normalization",
        question="How should asset aliases be normalized?",
        expected_answer_terms=["TX-0091", "Transformer 91", "TRF_91"],
        expected_context_terms=["Normalize asset identifier", "TX-0091", "Transformer 91", "TRF_91"],
        expected_source_files=["02_aquila_product_knowledge_base.md"],
        tags=["procedure", "aliases"],
    ),
    EvaluationCase(
        id="feeder-ambiguity",
        question="What can the term feeder mean in this corpus?",
        expected_answer_terms=["electrical", "Kafka"],
        expected_context_terms=["electrical feeder", "Kafka"],
        expected_source_files=[
            "01_aquila_operations_plain_text.txt",
            "03_aquila_security_runbook.markdown",
        ],
        tags=["ambiguity", "definition"],
    ),
)
