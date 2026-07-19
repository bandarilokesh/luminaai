import torch
from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
from config.settings import settings
from utils.logger import logger

# Lazy load NLI model
_nli_model = None
NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-small" # Fast, accurate NLI model

def get_nli_model() -> CrossEncoder:
    global _nli_model
    if _nli_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading NLI model '{NLI_MODEL_NAME}' on {device}...")
        os_env_cache = settings.CACHE_DIR / "huggingface"
        os_env_cache.mkdir(parents=True, exist_ok=True)
        # We use a cross-encoder trained on NLI (entailment, contradiction, neutral)
        _nli_model = CrossEncoder(
            NLI_MODEL_NAME,
            device=device,
            cache_folder=str(os_env_cache)
        )
        logger.info("NLI model loaded successfully.")
    return _nli_model

def verify_claim(claim: str, evidence_chunks: List[str]) -> Dict[str, Any]:
    """
    Verifies a single claim against a list of evidence chunks using NLI.
    Returns the verification status and the supporting chunk index if supported.
    """
    if not evidence_chunks:
        return {"status": "UNSUPPORTED", "evidence": None, "score": 0.0}
        
    try:
        model = get_nli_model()
        
        # Prepare pairs: (evidence, claim)
        # NLI typically takes premise and hypothesis
        pairs = [[chunk, claim] for chunk in evidence_chunks]
        
        # Get predictions
        # For deberta-v3-small-nli, labels are typically: 0: contradiction, 1: entailment, 2: neutral
        # Wait, the exact mapping depends on the model.
        # "cross-encoder/nli-deberta-v3-small" maps: 0: contradiction, 1: entailment, 2: neutral.
        # Let's get logits and apply softmax.
        logits = model.predict(pairs)
        
        best_entailment_score = -1.0
        best_chunk_idx = -1
        
        for idx, logit in enumerate(logits):
            # Apply softmax to get probabilities
            exp_logits = torch.exp(torch.tensor(logit))
            probs = exp_logits / torch.sum(exp_logits)
            
            # Index 1 is entailment for this model
            entailment_prob = probs[1].item()
            contradiction_prob = probs[0].item()
            
            if entailment_prob > best_entailment_score:
                best_entailment_score = entailment_prob
                best_chunk_idx = idx
                
        # Thresholds for entailment
        if best_entailment_score > 0.6:
            return {
                "status": "SUPPORTED",
                "evidence_idx": best_chunk_idx,
                "evidence_text": evidence_chunks[best_chunk_idx],
                "score": best_entailment_score
            }
        else:
            return {
                "status": "UNSUPPORTED",
                "evidence_idx": -1,
                "evidence_text": None,
                "score": best_entailment_score
            }
            
    except Exception as e:
        logger.error(f"NLI verification failed: {str(e)}")
        # Graceful fallback: assume unsupported if model fails
        return {"status": "ERROR", "evidence": None, "score": 0.0}

def verify_all_claims(claims: List[str], evidence_chunks: List[str]) -> List[Dict[str, Any]]:
    """Verifies a list of claims against evidence chunks."""
    results = []
    for claim in claims:
        results.append({
            "claim": claim,
            "verification": verify_claim(claim, evidence_chunks)
        })
    return results
