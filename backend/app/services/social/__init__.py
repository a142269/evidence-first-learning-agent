"""Social learning subpackage — peer matching & recommendation (Innovation #6)."""
from backend.app.services.social.peer_matching import PeerMatcher, get_peer_matcher
from backend.app.services.social.recommendation_engine import RecommendationEngine

__all__ = ["PeerMatcher", "get_peer_matcher", "RecommendationEngine"]
