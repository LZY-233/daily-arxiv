from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arxiv import Paper


@dataclass(slots=True)
class RankingResult:
    included: bool
    exclusion_reason: str | None


def _matches(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase.lower() in text]


def rank_paper(paper: Paper, config: dict[str, Any]) -> RankingResult:
    text = f"{paper.title} {paper.abstract_en}".lower()
    excluded: list[str] = []
    for label, phrases in config["vertical_exclusions"].items():
        if _matches(text, phrases):
            excluded.append(label)
    has_override = bool(_matches(text, config["foundation_overrides"]))
    if excluded and not has_override:
        return RankingResult(False, ", ".join(excluded))

    topics: list[str] = []
    relevance = 0.0
    why: list[str] = []
    for topic in config["topics"]:
        found = _matches(text, topic["phrases"])
        if not found:
            continue
        topics.append(topic["id"])
        if topic["priority"] == "low":
            contribution = -12.0
        else:
            contribution = float(topic["weight"]) + min(len(found) - 1, 2) * 1.5
        relevance += contribution
        why.append(f"匹配 {topic['label']}：{', '.join(found[:3])}")

    if not topics:
        return RankingResult(False, "no-topic-match")

    evidence_score = 0.0
    evidence: list[str] = []
    signal_weights = {"method": 10, "scale": 8, "evidence": 12, "openness": 6}
    signal_labels = {"method": "明确的方法贡献", "scale": "规模化信号", "evidence": "实验或理论证据信号", "openness": "开放资源信号"}
    for signal, phrases in config["quality_signals"].items():
        found = _matches(text, phrases)
        if found:
            evidence_score += signal_weights[signal] + min(len(found) - 1, 2) * 2
            evidence.append(f"{signal_labels[signal]}：{', '.join(found[:3])}")

    preference_boost = 0.0
    preference_penalty = 0.0
    for label, signal in config.get("preference_signals", {}).get("boost", {}).items():
        found = _matches(text, signal["phrases"])
        if found:
            preference_boost += float(signal["points"])
            why.append(f"偏好加分 {label}：{', '.join(found[:3])}")
    title_text = paper.title.lower()
    for label, signal in config.get("preference_signals", {}).get("title_penalty", {}).items():
        found = _matches(title_text, signal["phrases"])
        if found:
            preference_penalty += float(signal["points"])
            why.append(f"偏好降权 {label}：{', '.join(found[:3])}")

    relevance = max(0.0, min(relevance, 64.0))
    evidence_score = min(evidence_score, 36.0)
    overall = round(max(0.0, min(100.0, relevance + evidence_score + preference_boost - preference_penalty)), 1)
    paper.topics = topics
    paper.relevance_score = round(relevance, 1)
    paper.evidence_score = round(evidence_score, 1)
    paper.preference_boost = round(preference_boost, 1)
    paper.preference_penalty = round(preference_penalty, 1)
    paper.overall_score = overall
    paper.confidence = "medium" if evidence_score >= 20 else "low"
    paper.why_it_matters = why
    paper.evidence = evidence
    paper.limitations = ["当前仅检查标题和摘要，尚未核验正文、实验细节与可复现性。"]
    return RankingResult(True, None)


def _diverse_pick(
    candidates: list[Paper],
    count: int,
    penalty: float = 4.0,
    quality_band: float = 5.0,
) -> list[Paper]:
    """Greedily preserve quality while reducing same-topic saturation."""
    remaining = list(candidates)
    selected: list[Paper] = []
    topic_counts: dict[str, int] = {}
    umbrella_topics = {"llm", "reasoning", "efficiency", "evaluation", "safety"}
    while remaining and len(selected) < count:
        def adjusted_score(paper: Paper) -> tuple[float, str]:
            focus = [topic for topic in (paper.topics or []) if topic not in umbrella_topics]
            if not focus:
                focus = ["llm"]
            saturation = min((topic_counts.get(topic, 0) for topic in focus), default=0)
            return paper.overall_score - penalty * saturation, paper.updated_at

        best_raw_score = max(paper.overall_score for paper in remaining)
        eligible = [paper for paper in remaining if paper.overall_score >= best_raw_score - quality_band]
        best = max(eligible, key=adjusted_score)
        remaining.remove(best)
        selected.append(best)
        focus = [topic for topic in (best.topics or []) if topic not in umbrella_topics] or ["llm"]
        for topic in focus:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    return selected


def assign_tiers(papers: list[Paper], must_read_count: int, browse_count: int) -> list[Paper]:
    ranked = sorted(papers, key=lambda p: (p.overall_score, p.updated_at), reverse=True)
    must_read = _diverse_pick(ranked, must_read_count, quality_band=6.0)
    must_keys = {(paper.arxiv_id, paper.version) for paper in must_read}
    remaining = [paper for paper in ranked if (paper.arxiv_id, paper.version) not in must_keys]
    browse = _diverse_pick(remaining, browse_count, penalty=2.5, quality_band=4.0)
    browse_keys = {(paper.arxiv_id, paper.version) for paper in browse}
    watch = [paper for paper in remaining if (paper.arxiv_id, paper.version) not in browse_keys]
    for paper in must_read:
        paper.tier = "must_read"
    for paper in browse:
        paper.tier = "browse"
    for paper in watch:
        paper.tier = "watch"
    return must_read + browse + watch
