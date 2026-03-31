from reddit_kb.reddit_thread import extract_top_comments_from_thread_json


def test_extract_top_comments_skips_more_and_sorts_by_score():
    root = [
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {"kind": "t3", "data": {"id": "p1", "title": "x"}},
                ],
            },
        },
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "id": "c_low",
                            "body": "low",
                            "score": 1,
                            "replies": "",
                        },
                    },
                    {"kind": "more", "data": {}},
                    {
                        "kind": "t1",
                        "data": {
                            "id": "c_high",
                            "body": "high",
                            "score": 99,
                            "replies": "",
                        },
                    },
                ],
            },
        },
    ]
    out = extract_top_comments_from_thread_json(
        root,
        top_n=5,
        max_comment_chars=100,
        max_comment_depth=2,
    )
    assert len(out) == 2
    assert out[0].id == "c_high"
    assert out[0].score == 99
    assert out[1].id == "c_low"


def test_skips_removed():
    root = [
        {"kind": "Listing", "data": {"children": []}},
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {"kind": "t1", "data": {"id": "r1", "body": "[removed]", "score": 10}},
                ],
            },
        },
    ]
    assert extract_top_comments_from_thread_json(
        root,
        top_n=5,
        max_comment_chars=100,
        max_comment_depth=2,
    ) == []
