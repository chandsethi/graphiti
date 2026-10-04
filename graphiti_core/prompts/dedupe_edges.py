"""
Copyright 2024, Zep Software, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from typing import Any, Protocol, TypedDict

from pydantic import BaseModel, Field

from .models import Message, PromptFunction, PromptVersion


class EdgeDuplicate(BaseModel):
    duplicate_facts: list[int] = Field(
        ...,
        description='List of idx values of duplicate facts (only from EXISTING FACTS range). Empty list if none.',
    )
    contradicted_facts: list[int] = Field(
        ...,
        description='List of idx values of contradicted facts (from full idx range). Empty list if none.',
    )
    is_correction: bool = Field(
        default=False,
        description='True if the NEW FACT explicitly corrects or updates an old fact (e.g., moved from A to B, changed from X to Y). False for genuine disagreements or conflicts where both could be true in different contexts.',
    )


class Prompt(Protocol):
    resolve_edge: PromptVersion


class Versions(TypedDict):
    resolve_edge: PromptFunction


def resolve_edge(context: dict[str, Any]) -> list[Message]:
    return [
        Message(
            role='system',
            content='You are a fact deduplication and resolution assistant. '
            'You handle facts, plans, and ideas differently based on their kind. '
            'NEVER mark facts with key differences as duplicates.',
        ),
        Message(
            role='user',
            content=f"""
NEVER mark facts as duplicates if they have key differences, particularly around numeric values, dates, or key qualifiers.

IMPORTANT constraints:
- duplicate_facts: ONLY idx values from EXISTING FACTS (NEVER include FACT INVALIDATION CANDIDATES)
- contradicted_facts: idx values from EITHER list (EXISTING FACTS or FACT INVALIDATION CANDIDATES)
- The idx values are continuous across both lists (INVALIDATION CANDIDATES start where EXISTING FACTS end)
- is_correction: True only when the NEW FACT explicitly corrects an old fact or describes a change of state over time

<EXISTING FACTS>
{context['existing_edges']}
</EXISTING FACTS>

<FACT INVALIDATION CANDIDATES>
{context['edge_invalidation_candidates']}
</FACT INVALIDATION CANDIDATES>

<NEW FACT>
{context['new_edge']}
</NEW FACT>

You will receive TWO lists of facts with CONTINUOUS idx numbering across both lists.
EXISTING FACTS are indexed first, followed by FACT INVALIDATION CANDIDATES.

# KIND-AWARE RESOLUTION RULES

The NEW FACT has a "kind" field: "fact", "plan", or "idea". Apply different rules based on kind:

## FACT (stable statements)
1. DUPLICATE DETECTION: If identical to an existing fact, mark as duplicate.
2. CONTRADICTION DETECTION:
   - If the NEW FACT explicitly corrects or updates an old fact (e.g., "moved from Delhi to Bangalore", "changed title from X to Y"), mark the old fact as contradicted AND set is_correction=True.
   - If the NEW FACT contradicts an old fact but is NOT a correction (e.g., two different sources say different things, genuine disagreement), mark as contradicted but set is_correction=False. The old fact will be kept and marked as conflicting rather than invalidated.

## PLAN (intended future actions)
1. DUPLICATE DETECTION: If identical to an existing plan, mark as duplicate.
2. CONTRADICTION DETECTION: If the NEW FACT is a plan about the same subject/goal as an existing plan, mark the old plan as contradicted (the new plan supersedes it). Set is_correction=True.

## IDEA (speculative thoughts)
1. DUPLICATE DETECTION: Only mark as duplicate if the idea is identical.
2. CONTRADICTION DETECTION: Ideas NEVER contradict facts or plans, and facts/plans never contradict ideas. An idea can only duplicate another identical idea.

<EXAMPLES>
EXISTING FACT (kind=fact): idx=0, "Alice joined Acme Corp in 2020"
NEW FACT (kind=fact): "Alice joined Acme Corp in 2020"
Result: duplicate_facts=[0], contradicted_facts=[], is_correction=False (identical)

EXISTING FACT (kind=fact): idx=1, "Alice works at Acme Corp"
NEW FACT (kind=fact): "Alice works at TechCo"
Result: duplicate_facts=[], contradicted_facts=[1], is_correction=True (moved companies — correction)

EXISTING FACT (kind=fact): idx=2, "The capital of country X is City A" (from source 1)
NEW FACT (kind=fact): "The capital of country X is City B" (from source 2)
Result: duplicate_facts=[], contradicted_facts=[2], is_correction=False (disagreement, not correction — both kept and marked as conflict)

EXISTING FACT (kind=plan): idx=3, "Bob plans to interview candidates next Tuesday"
NEW FACT (kind=plan): "Bob plans to interview candidates next Friday"
Result: duplicate_facts=[], contradicted_facts=[3], is_correction=True (new plan supersedes old)

EXISTING FACT (kind=fact): idx=4, "Alice works at Acme Corp"
NEW FACT (kind=idea): "Alice is considering switching to TechCo"
Result: duplicate_facts=[], contradicted_facts=[] (idea doesn't contradict fact)

EXISTING FACT (kind=idea): idx=5, "Bob might travel to Japan"
NEW FACT (kind=plan): "Bob plans to travel to France"
Result: duplicate_facts=[], contradicted_facts=[] (plan doesn't contradict idea; different subjects anyway)

EXISTING FACT (kind=idea): idx=6, "The team discussed possibly trying React"
NEW FACT (kind=idea): "The team discussed possibly trying React"
Result: duplicate_facts=[6], contradicted_facts=[] (identical idea)
</EXAMPLES>
""",
        ),
    ]


versions: Versions = {'resolve_edge': resolve_edge}
