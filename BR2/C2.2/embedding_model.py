import logging
from sentence_transformers import SentenceTransformer

_logger = logging.getLogger(__name__)
_model = None

def get_encoder():
    global _model
    if _model is None:
        _logger.info("Loading embedding model 'all-MiniLM-L6-v2'...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model
