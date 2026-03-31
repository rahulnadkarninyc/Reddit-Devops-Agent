from reddit_kb.models import PostRecord


def test_post_record_from_reddit_child():
    child = {
        "kind": "t3",
        "data": {
            "id": "abc123",
            "name": "t3_abc123",
            "subreddit": "devops",
            "title": "How do I CI?",
            "selftext": "body",
            "score": 42,
            "num_comments": 7,
            "created_utc": 1700000000.0,
            "permalink": "/r/devops/comments/x/yo/",
            "url": "https://reddit.com/...",
        },
    }
    rec = PostRecord.from_reddit_child(child, "month")
    assert rec is not None
    assert rec.id == "abc123"
    assert rec.fullname == "t3_abc123"
    assert rec.subreddit == "devops"
    assert rec.schema_version == 2
    assert rec.top_comments == []


def test_non_post_child():
    assert PostRecord.from_reddit_child({"kind": "t1", "data": {}}, "month") is None
