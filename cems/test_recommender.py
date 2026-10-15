from comment_extractor import Config, LLMClient
from recommender.resolution_recommender import recommend_resolution

cfg = Config.from_yaml("config.yaml")
llm = LLMClient(cfg)

test_comments = [
    "Check that the pipe size agrees with the approved hydraulic schedule.",
    "Weld size not per AWS D1.1, please verify fillet weld dimensions",
    "Relocate this valve to maintain maintenance clearance.",
    "Font on the title block is too small to read",
]

for comment in test_comments:
    result = recommend_resolution(comment, llm)
    print(f"\n{'='*60}")
    print(f"COMMENT: {comment}")
    print(f"DRAFT: {result['draft_resolution']}")
    print(f"BASIS: {result['basis']} | CONFIDENCE: {result['confidence_percent']}%")