"""Document ingestion helpers for travel knowledge."""

from typing import Iterable, List

from .knowledge_schema import TravelKnowledgeDoc


def load_seed_knowledge() -> List[TravelKnowledgeDoc]:
    """Return built-in travel planning knowledge used before an external KB exists."""
    return [
        TravelKnowledgeDoc(
            doc_id="general-city-routing",
            doc_type="city",
            city="",
            title="城市动线规划原则",
            content="多日行程应按区域聚合景点，避免同一天跨城或跨多个远距离区域移动。每天安排2到3个核心景点更稳妥。",
            tags=["动线", "交通", "轻松", "城市"],
        ),
        TravelKnowledgeDoc(
            doc_id="general-weather-adaptation",
            doc_type="travel_tip",
            city="",
            title="天气适配建议",
            content="雨天、高温或大风天气应减少户外暴走，优先安排博物馆、商场、室内展馆、美食街等替代方案。",
            tags=["天气", "雨天", "室内", "高温"],
        ),
        TravelKnowledgeDoc(
            doc_id="general-family-elder",
            doc_type="user_preference",
            city="",
            title="亲子和老人旅行节奏",
            content="亲子、老人、轻松游偏好下，每天核心点位不宜超过3个，应保留午休、就餐和交通缓冲时间。",
            tags=["亲子", "老人", "轻松", "节奏"],
        ),
        TravelKnowledgeDoc(
            doc_id="beijing-city-areas",
            doc_type="city",
            city="北京",
            title="北京热门区域",
            content="北京适合按故宫与天安门、什刹海与鼓楼、颐和园与圆明园、798与朝阳公园等区域组合行程。",
            tags=["北京", "区域", "历史文化"],
        ),
        TravelKnowledgeDoc(
            doc_id="shanghai-city-areas",
            doc_type="city",
            city="上海",
            title="上海热门区域",
            content="上海可按外滩与南京东路、人民广场与博物馆、徐汇衡复风貌区、陆家嘴与浦东滨江等区域组织路线。",
            tags=["上海", "区域", "城市漫步"],
        ),
        TravelKnowledgeDoc(
            doc_id="tokyo-anime-food",
            doc_type="attraction",
            city="东京",
            title="东京动漫与美食路线",
            content="动漫偏好可考虑秋叶原、池袋、中野Broadway、三鹰之森吉卜力美术馆。美食建议跟随当天区域嵌入，而不是单独跨区安排。",
            tags=["东京", "动漫", "美食", "轻松"],
        ),
    ]


def ingest_documents(raw_docs: Iterable[dict]) -> List[TravelKnowledgeDoc]:
    """Validate external raw docs into TravelKnowledgeDoc objects."""
    return [TravelKnowledgeDoc.model_validate(doc) for doc in raw_docs]
