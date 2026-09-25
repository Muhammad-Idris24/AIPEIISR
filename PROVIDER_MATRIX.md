# Provider Matrix

| Capability | MVP provider | Free/developer basis | Fallback | Production decision |
|---|---|---|---|---|
| LLM/extraction | Deterministic local mock | No account or external data transfer | Safe “analysis unavailable” result | OPEN DECISION: approved provider/data terms |
| Embeddings | Deterministic local hash vector | No account | Disable similarity ranking | PostgreSQL pgvector + approved embedding provider |
| Search/evidence | Internal collected knowledge | No external dependency | Return insufficient evidence | Approved partner/search adapter |
| RSS | feedparser + approved feeds | Open-source client; terms per source | Source health failure | Approved registry |
| OCR/transcription/media | Metadata/hash triage only | Local implementation | Analysis unavailable | OPEN DECISION |
| Hosted inference | Hugging Face Inference Providers | Official docs list limited monthly credits | Mock/Ollama | Evaluate account, data terms and cost |
| Local inference | Ollama adapter | Local host controlled | Mock | Hardware/security review |
