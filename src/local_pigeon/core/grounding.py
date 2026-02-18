"""
Grounding Classifier

Detects when a user query needs web search for factual grounding.
Uses a two-stage approach:
1. Fast regex patterns for obvious cases
2. Lightweight LLM classifier for uncertain cases

This ensures the model gets accurate, up-to-date information
for factual questions rather than relying on training data.
"""

import re
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_pigeon.core.llm_client import OllamaClient

logger = logging.getLogger(__name__)


@dataclass
class GroundingResult:
    """Result of grounding classification."""
    needs_grounding: bool
    confidence: float  # 0.0 to 1.0
    reason: str
    suggested_query: str | None = None


# Fast regex patterns that DEFINITELY need grounding
# These are high-confidence patterns that avoid the need for LLM classification
DEFINITE_GROUNDING_PATTERNS = [
    # Current events / time-sensitive - flexible word order
    (r"\b(who is|who's)\b.*(president|ceo|leader|head|founder|owner|chairman)\b", "current position holder"),
    (r"\b(president|ceo|leader|head|founder|owner|chairman)\b.*(who is|who's)\b", "current position holder"),
    (r"\bwho\b.*(president|ceo|leader)\b", "current position holder"),  # Simplified: "who" + position word
    (r"\b(tell me|can you tell me|do you know)\b.*\b(who|what|when|where)\b", "question request"),  # "tell me who..."
    (r"\b(current|latest|recent|today'?s?) (president|leader|ceo|news|price|score|results|weather)\b", "current events"),
    (r"\b(bitcoin|btc|eth|stock|crypto) (price|value|worth)\b", "price lookup"),
    (r"\b(weather|temperature|forecast) (in|for|today|tomorrow)\b", "weather lookup"),
    
    # Sports / competitions / elections
    (r"\b(who won|winner of|score of|results of|results for)\b", "event results"),
    (r"\b(election|super bowl|world cup|olympics)\b.*(results?|winner|won)\b", "event results"),
    (r"\b(results?|winner|won)\b.*(election|super bowl|world cup|olympics)\b", "event results"),
    (r"\b(super bowl|world series|world cup|olympics)\b.*(winner|won|score|champion|result)\b", "sports/competition results"),
    (r"\b(20\d\d)\b.*(super bowl|world cup|olympics|election|champion)\b", "dated event lookup"),
    
    # People in positions
    (r"\bwho (runs|leads|heads|owns|founded|started)\b", "position lookup"),
    (r"\b(president|ceo|leader|founder) of\b", "position lookup"),
    
    # Fact verification
    (r"\b(is it true|fact check|verify|confirm)\b", "fact verification"),
    (r"\b(how many|how much|what percentage|what number)\b", "quantitative fact"),
    
    # Historical facts with specific dates/numbers
    (r"\b(when did|what year|what date)\b", "historical date"),
    (r"\b(invented|discovered|founded|created|started) (in|by)\b", "historical fact"),
    
    # Recommendations / local search (restaurants, places, businesses)
    (r"\b(best|top|good|great|popular|recommended|highest rated)\b.*\b(restaurant|cafe|bar|pub|shop|store|place|hotel|gym|salon|clinic|dentist|doctor|mechanic)", "recommendation lookup"),
    (r"\b(restaurant|cafe|bar|pub|shop|store|place|hotel|gym|salon|clinic)s?\b.*\b(near|in|around|close to|nearby)\b", "local search"),
    (r"\b(where (can i|should i|to) (eat|drink|get|buy|find))\b", "local recommendation"),
    (r"\b(yelp|tripadvisor|google reviews|opentable|zomato)\b", "review site lookup"),
    (r"\b(recommend|suggestion|recommend me|suggest)\b.*\b(restaurant|food|place|eat|drink|coffee|lunch|dinner|breakfast|brunch)\b", "recommendation request"),
    (r"\b(food|eat|dining|lunch|dinner|breakfast|brunch|coffee)\b.*\b(near|nearby|around|close|in town)\b", "local food search"),
]

# Patterns that PROBABLY need grounding (medium confidence)
PROBABLE_GROUNDING_PATTERNS = [
    (r"\bwhat is (the|a)\b", "definition/fact query"),
    (r"\bwho is\b", "person lookup"),
    (r"\b(tell me about|explain|describe)\b", "information request"),
]

# Patterns that likely DON'T need grounding (personal/subjective)
# NOTE: These only apply when NO factual patterns are matched first
NO_GROUNDING_PATTERNS = [
    # Creative writing - must be explicitly asking to write/create something
    r"\b(write|create|generate|compose|draft)\b.*\b(story|poem|code|script|letter)\b",
    # Code help - must be about coding specifically
    r"\b(how do i|how can i|help me)\b.*\b(code|program|implement|debug|fix.*error)\b",
    # Pure greetings (without questions)
    r"^(hello|hi|hey|thanks|thank you)[\s.,!?]*$",
    # Opinion questions
    r"\bwhat do you (think|feel|believe)\b",
    r"\bwhat('s| is) your opinion\b",
]


class GroundingClassifier:
    """
    Classifies user queries to determine if web search is needed.
    
    Uses fast patterns first, then optional LLM classification for
    uncertain cases.
    """
    
    def __init__(self, llm_client: "OllamaClient | None" = None):
        """
        Initialize the classifier.
        
        Args:
            llm_client: Optional LLM client for uncertain cases.
                       If not provided, falls back to pattern-only classification.
        """
        self.llm = llm_client
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._definite_patterns = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in DEFINITE_GROUNDING_PATTERNS
        ]
        self._probable_patterns = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in PROBABLE_GROUNDING_PATTERNS
        ]
        self._no_grounding_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in NO_GROUNDING_PATTERNS
        ]
    
    def classify_fast(self, query: str) -> GroundingResult:
        """
        Fast pattern-based classification (no LLM call).
        
        Returns a result with confidence based on pattern matches.
        PRIORITY ORDER: Definite YES patterns checked BEFORE NO patterns,
        because factual signals are stronger than creative signals.
        """
        query_lower = query.lower()
        
        # Check definite YES grounding patterns FIRST (stronger signal)
        for pattern, reason in self._definite_patterns:
            if pattern.search(query_lower):
                return GroundingResult(
                    needs_grounding=True,
                    confidence=0.95,
                    reason=reason,
                    suggested_query=self._extract_search_query(query),
                )
        
        # Check definite NO grounding patterns (only if no factual patterns matched)
        for pattern in self._no_grounding_patterns:
            if pattern.search(query_lower):
                return GroundingResult(
                    needs_grounding=False,
                    confidence=0.8,
                    reason="creative/personal request",
                )
        
        # Check probable grounding patterns
        for pattern, reason in self._probable_patterns:
            if pattern.search(query_lower):
                return GroundingResult(
                    needs_grounding=True,
                    confidence=0.6,
                    reason=reason,
                    suggested_query=self._extract_search_query(query),
                )
        
        # Default: uncertain, low confidence no
        return GroundingResult(
            needs_grounding=False,
            confidence=0.3,
            reason="no clear factual indicators",
        )
    
    async def classify(self, query: str, use_llm: bool = True) -> GroundingResult:
        """
        Classify a query for grounding needs.
        
        Args:
            query: The user's question
            use_llm: Whether to use LLM for uncertain cases
            
        Returns:
            GroundingResult with classification details
        """
        # First, try fast pattern matching
        result = self.classify_fast(query)
        
        # If high confidence, return immediately
        if result.confidence >= 0.7:
            logger.debug(f"Grounding fast-path: {result.needs_grounding} ({result.reason})")
            return result
        
        # If LLM available and uncertain, do a quick classification
        if use_llm and self.llm is not None:
            return await self._classify_with_llm(query)
        
        return result
    
    async def _classify_with_llm(self, query: str) -> GroundingResult:
        """
        Use a lightweight LLM call to classify the query.
        
        This is a fast, focused call just for classification.
        """
        from local_pigeon.core.llm_client import Message
        
        classification_prompt = """Classify this user query. Reply with ONLY one word: SEARCH or CHAT

SEARCH = needs web search for current/factual info (dates, people in positions, prices, events, facts)
CHAT = can be answered from general knowledge or is a creative/personal request

Query: "{query}"
Reply:"""
        
        try:
            messages = [
                Message(role="user", content=classification_prompt.format(query=query))
            ]
            
            # Quick call with no tools, just classification
            # Use achat (async) without stream parameter - it's not supported
            response = await self.llm.achat(
                messages=messages,
                tools=None,
            )
            
            answer = response.content.strip().upper() if response.content else ""
            
            if "SEARCH" in answer:
                return GroundingResult(
                    needs_grounding=True,
                    confidence=0.85,
                    reason="LLM classified as needing search",
                    suggested_query=self._extract_search_query(query),
                )
            else:
                return GroundingResult(
                    needs_grounding=False,
                    confidence=0.85,
                    reason="LLM classified as conversational",
                )
                
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to pattern")
            return self.classify_fast(query)
    
    def _extract_search_query(self, query: str) -> str:
        """
        Extract a clean search query from the user's message.
        
        Removes conversational fluff and focuses on the factual question.
        """
        # Remove common prefixes
        prefixes = [
            r"^(hey |hi |hello |please |can you |could you |would you |i want to know |tell me |what is |what's |who is |who's )",
            r"^(do you know |i'm curious |i was wondering |quick question |)",
        ]
        
        cleaned = query.strip()
        for prefix in prefixes:
            cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE)
        
        # Remove trailing punctuation and extra whitespace
        cleaned = re.sub(r"[?.!]+$", "", cleaned).strip()
        
        return cleaned if cleaned else query


async def preflight_grounding(
    query: str,
    llm_client: "OllamaClient",
    web_search_tool,
    use_llm_classification: bool = True,
) -> tuple[str | None, GroundingResult]:
    """
    Run grounding preflight check and optionally fetch search results.
    
    This should be called BEFORE the main chat to inject grounding
    context when needed.
    
    Args:
        query: The user's question
        llm_client: LLM client (for classification if needed)
        web_search_tool: The web_search tool instance
        use_llm_classification: Whether to use LLM for uncertain cases
        
    Returns:
        Tuple of (search_results or None, GroundingResult)
    """
    classifier = GroundingClassifier(llm_client if use_llm_classification else None)
    result = await classifier.classify(query, use_llm=use_llm_classification)
    
    if not result.needs_grounding:
        return None, result
    
    # Perform the search
    search_query = result.suggested_query or query
    logger.info(f"Grounding preflight: searching for '{search_query}'")
    
    try:
        # Execute web search
        search_result = await web_search_tool.execute(query=search_query, num_results=5)
        
        if search_result and "Error" not in search_result:
            return search_result, result
        else:
            logger.warning(f"Grounding search failed: {search_result}")
            return None, result
            
    except Exception as e:
        logger.warning(f"Grounding preflight search error: {e}")
        return None, result
