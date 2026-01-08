# Agent Expertise Plan: Becoming an Expert on Streamer + Chat

## Current State Analysis

### What We Have
1. **Vector Search**: Semantic search over transcript+chat snippets with reranking
2. **Viral Detection**: Proprietary scoring system for clip-worthy moments
3. **Chat Summarization**: LLM-based summaries with affect tags and request verbs
4. **Basic Q&A**: Grounded answers with citations and timestamps
5. **Data Pipeline**: Automated download, transcription, and processing of VODs

### What's Missing for True Expertise
1. **Streamer Personality Profile**: Understanding the streamer's style, preferences, catchphrases
2. **Chat Community Patterns**: Regular viewers, memes, inside jokes, community culture
3. **Temporal Understanding**: How streamer/chat evolved over time, trends, patterns
4. **Content Preferences**: Games played, content types, recurring themes
5. **Relationship Dynamics**: How streamer interacts with chat, response patterns
6. **Predictive Capabilities**: What content will resonate, when to stream what
7. **Contextual Memory**: Cross-session understanding, building on previous conversations
8. **Deep Semantic Understanding**: Beyond keyword matching to true comprehension

---

## Proposed Enhancement Strategy

### Phase 1: Streamer Profile Building

#### 1.1 Streamer Personality Extraction
**Goal**: Build a comprehensive personality profile from all transcripts

**Implementation**:
- Create a new tool: `get_streamer_profile(twitch_username)` that:
  - Analyzes all transcripts to extract:
    - **Catchphrases & Signature Phrases**: Most repeated phrases, unique expressions
    - **Communication Style**: Formal/casual, humor type, energy levels
    - **Content Preferences**: Games mentioned, topics discussed frequently
    - **Values & Opinions**: Recurring opinions, stances on topics
    - **Behavioral Patterns**: How they react to different situations
  - Uses LLM to synthesize a "Streamer Profile" document
  - Updates incrementally as new VODs are processed

**Data Structure**:
```python
class StreamerProfile(BaseModel):
    catchphrases: list[str]  # Top 20-30 unique phrases
    communication_style: str  # LLM-generated description
    favorite_games: list[str]  # Games mentioned most
    content_themes: list[str]  # Recurring topics
    personality_traits: list[str]  # Extracted traits
    signature_reactions: dict[str, str]  # How they react to different situations
    last_updated: datetime
```

#### 1.2 Streamer Knowledge Graph
**Goal**: Build relationships between concepts, games, people, events

**Implementation**:
- Extract entities (games, people, events, topics) from all transcripts
- Build relationships: "streamer plays X game", "streamer mentions Y person", "streamer reacts to Z event"
- Store in a graph structure for complex queries like:
  - "What games did the streamer play when chat was most hyped?"
  - "Who does the streamer collaborate with most?"

**Tools**:
- `get_streamer_entities(twitch_username, entity_type=None)` - Get all entities of a type
- `get_entity_relationships(twitch_username, entity)` - Get relationships for an entity
- `analyze_streamer_patterns(twitch_username, pattern_type)` - Find patterns

---

### Phase 2: Chat Community Intelligence

#### 2.1 Chat Community Profile
**Goal**: Understand the chat community as a collective entity

**Implementation**:
- Analyze chat messages across all VODs to identify:
  - **Regular Viewers**: Most active chatters, their patterns
  - **Community Memes**: Recurring jokes, references, inside jokes
  - **Chat Culture**: Overall vibe, norms, what's acceptable
  - **Engagement Patterns**: When chat is most active, what triggers engagement
  - **Sentiment Trends**: How community sentiment changes over time

**Data Structure**:
```python
class ChatCommunityProfile(BaseModel):
    regular_viewers: list[dict]  # Top chatters with stats
    memes_and_jokes: list[str]  # Recurring community memes
    community_culture: str  # LLM-generated description
    engagement_patterns: dict  # When/why chat engages
    sentiment_evolution: list[dict]  # Sentiment over time
    inside_jokes: list[str]  # References only community would understand
```

#### 2.2 Chat-Streamer Interaction Analysis
**Goal**: Understand the bidirectional relationship

**Implementation**:
- Analyze when streamer responds to chat vs. ignores
- Identify what types of chat messages get responses
- Map chat reactions to streamer actions
- Understand chat's influence on streamer decisions

**Tools**:
- `analyze_chat_streamer_interactions(twitch_username, video_id=None)`
- `get_chat_influence_moments(twitch_username)` - When chat influenced streamer
- `get_streamer_response_patterns(twitch_username)` - What chat gets responses

---

### Phase 3: Temporal & Trend Analysis

#### 3.1 Evolution Tracking
**Goal**: Understand how streamer and chat evolved over time

**Implementation**:
- Track changes in:
  - Streamer's content preferences over time
  - Chat community growth and changes
  - Sentiment trends
  - Viral moment patterns
  - Game/content shifts

**Tools**:
- `get_streamer_evolution(twitch_username, metric)` - Track specific metrics over time
- `identify_trends(twitch_username, time_period)` - Find trends in a period
- `compare_periods(twitch_username, period1, period2)` - Compare two time periods

#### 3.2 Predictive Analytics
**Goal**: Predict what content will resonate

**Implementation**:
- Analyze patterns in viral moments to identify:
  - What game/content combinations work best
  - Optimal streaming times based on chat engagement
  - Content types that generate most engagement
  - Predict future viral moments

**Tools**:
- `predict_viral_potential(twitch_username, content_description)` - Predict if content will be viral
- `recommend_content(twitch_username)` - Suggest content based on patterns
- `optimal_streaming_insights(twitch_username)` - Best times/content for engagement

---

### Phase 4: Advanced Query Capabilities

#### 4.1 Complex Multi-Hop Reasoning
**Goal**: Answer complex questions requiring multiple data points

**Examples**:
- "What was the streamer's reaction when chat was most hyped about a new game?"
- "Show me moments where the streamer changed their mind based on chat feedback"
- "What games generate the most positive chat sentiment?"

**Implementation**:
- Enhanced `search_and_cite` with multi-query decomposition
- Chain multiple tool calls to answer complex questions
- Synthesize information from multiple sources

#### 4.2 Comparative Analysis
**Goal**: Compare different aspects of the streamer/chat

**Tools**:
- `compare_games(twitch_username, game1, game2)` - Compare engagement across games
- `compare_periods(twitch_username, period1, period2)` - Compare time periods
- `compare_chat_sentiment(twitch_username, topic1, topic2)` - Compare sentiment on topics

#### 4.3 Contextual Understanding
**Goal**: Understand context beyond individual moments

**Implementation**:
- Build context windows around moments
- Understand narrative arcs across streams
- Track ongoing storylines or themes
- Connect related moments across different VODs

**Tools**:
- `get_context_around_moment(twitch_username, video_id, timestamp, window_sec)` - Get extended context
- `find_related_moments(twitch_username, moment_description)` - Find related moments
- `track_narrative_arc(twitch_username, topic)` - Track a topic across multiple streams

---

### Phase 5: Agent Memory & Learning

#### 5.1 Session Memory
**Goal**: Remember context within a conversation

**Implementation**:
- Store conversation history
- Build on previous questions/answers
- Reference earlier parts of conversation
- Maintain context about what user is interested in

#### 5.2 Long-term Learning
**Goal**: Learn from interactions to improve responses

**Implementation**:
- Track which answers were helpful
- Learn user preferences
- Adapt response style based on user feedback
- Build a knowledge base of common questions

#### 5.3 Proactive Insights
**Goal**: Provide insights without being asked

**Implementation**:
- Identify interesting patterns automatically
- Surface anomalies or notable changes
- Suggest questions user might want to ask
- Highlight new trends or patterns

---

## Implementation Priority

### High Priority (Immediate Value)
1. **Streamer Profile Building** (Phase 1.1) - Foundation for all other features
2. **Chat Community Profile** (Phase 2.1) - Understand the community
3. **Enhanced Multi-Hop Queries** (Phase 4.1) - Better answers to complex questions

### Medium Priority (Significant Value)
4. **Temporal Analysis** (Phase 3.1) - Understand evolution
5. **Chat-Streamer Interactions** (Phase 2.2) - Understand relationship dynamics
6. **Contextual Understanding** (Phase 4.3) - Better context around moments

### Lower Priority (Nice to Have)
7. **Predictive Analytics** (Phase 3.2) - Future predictions
8. **Knowledge Graph** (Phase 1.2) - Complex entity relationships
9. **Session Memory** (Phase 5.1) - Conversation continuity

---

## Technical Implementation Details

### New Data Structures Needed

```python
# Streamer Profile
class StreamerProfile(BaseModel):
    twitch_username: str
    catchphrases: list[dict]  # phrase, frequency, examples
    communication_style: str
    favorite_games: list[dict]  # game, mention_count, last_mentioned
    content_themes: list[str]
    personality_traits: list[str]
    signature_reactions: dict[str, list[dict]]  # reaction_type -> examples
    created_at: datetime
    updated_at: datetime

# Chat Community Profile
class ChatCommunityProfile(BaseModel):
    twitch_username: str
    regular_viewers: list[dict]  # username, message_count, first_seen, last_seen
    memes_and_jokes: list[dict]  # meme, frequency, examples
    community_culture: str
    engagement_patterns: dict  # time_of_day, day_of_week, content_type -> engagement
    sentiment_evolution: list[dict]  # timestamp, sentiment_score
    inside_jokes: list[str]
    created_at: datetime
    updated_at: datetime

# Temporal Analysis
class TemporalAnalysis(BaseModel):
    twitch_username: str
    metric: str  # e.g., "chat_velocity", "viral_moments", "game_preferences"
    time_series: list[dict]  # timestamp, value
    trends: list[dict]  # trend_type, description, confidence
```

### New Tools to Add

```python
# Profile Tools
def get_streamer_profile(twitch_username: str) -> dict
def get_chat_community_profile(twitch_username: str) -> dict
def update_profiles(twitch_username: str) -> dict  # Regenerate profiles

# Analysis Tools
def analyze_streamer_patterns(twitch_username: str, pattern_type: str) -> dict
def analyze_chat_streamer_interactions(twitch_username: str, video_id: str | None = None) -> dict
def get_streamer_evolution(twitch_username: str, metric: str) -> dict
def identify_trends(twitch_username: str, time_period: str | None = None) -> dict

# Advanced Query Tools
def compare_games(twitch_username: str, game1: str, game2: str) -> dict
def get_context_around_moment(twitch_username: str, video_id: str, timestamp: float, window_sec: int = 60) -> dict
def find_related_moments(twitch_username: str, moment_description: str) -> list[dict]

# Predictive Tools
def predict_viral_potential(twitch_username: str, content_description: str) -> dict
def recommend_content(twitch_username: str) -> dict
```

### Profile Generation Process

1. **Streamer Profile Generation**:
   - Extract all streamer transcripts
   - Use LLM to analyze and extract:
     - Catchphrases (frequency analysis + LLM validation)
     - Communication style (LLM analysis)
     - Content preferences (entity extraction + frequency)
     - Personality traits (LLM analysis)
   - Store in `streamers/{username}/profile.json`

2. **Chat Community Profile Generation**:
   - Aggregate all chat messages
   - Identify regular viewers (frequency analysis)
   - Extract memes (pattern detection + LLM validation)
   - Analyze engagement patterns (time-series analysis)
   - Generate community culture description (LLM analysis)
   - Store in `streamers/{username}/chat_profile.json`

3. **Temporal Analysis**:
   - Process VODs chronologically
   - Track metrics over time
   - Identify trends using statistical analysis
   - Store time-series data in `streamers/{username}/temporal_analysis.json`

---

## Agent Prompt Enhancements

### Updated Agent Instructions

Add to `TWITCH_AGENT` prompt:

```
Expert Knowledge:
- You have deep knowledge of the streamer's personality, catchphrases, and style
- You understand the chat community's culture, memes, and inside jokes
- You can track how the streamer and chat have evolved over time
- You can answer complex questions requiring multiple data points

New Capabilities:
- get_streamer_profile(twitch_username) -> StreamerProfile
- get_chat_community_profile(twitch_username) -> ChatCommunityProfile
- analyze_streamer_patterns(twitch_username, pattern_type) -> Analysis
- compare_games(twitch_username, game1, game2) -> Comparison
- get_context_around_moment(...) -> Extended context

Expert Behavior:
- Reference streamer's catchphrases and style naturally in answers
- Explain community memes and inside jokes when relevant
- Provide temporal context (e.g., "This was during their Valorant phase")
- Make connections across different VODs and time periods
- Use profile knowledge to provide richer, more contextual answers
```

---

## Success Metrics

1. **Answer Quality**: Can answer complex, multi-faceted questions
2. **Contextual Understanding**: References streamer personality and chat culture naturally
3. **Temporal Awareness**: Understands evolution and trends
4. **Predictive Accuracy**: Predictions about content performance are accurate
5. **User Satisfaction**: Users feel the agent truly "knows" the streamer and chat

---

## Next Steps

1. **Start with Streamer Profile**: Implement `get_streamer_profile()` tool
2. **Add Chat Community Profile**: Implement `get_chat_community_profile()` tool
3. **Enhance Agent Prompt**: Update instructions to use new knowledge
4. **Test with Complex Queries**: Validate improvements with real questions
5. **Iterate**: Refine based on usage patterns

