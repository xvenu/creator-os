"""Phase 7 API: reality, sources, assets, verify, artists, labels, newsroom, documentary."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["phase7"])


@router.get("/reality/report", summary="Reality Report for a topic")
def reality_report(topic: str, db: Session = Depends(get_db)):
    from app.modules.reality.engine import RealityEngine
    return RealityEngine.report(db, topic, actor="api")


@router.post("/reality/discover", summary="Discover official sources")
def reality_discover(db: Session = Depends(get_db)):
    from app.modules.reality.engine import SourceDiscoveryEngine
    return SourceDiscoveryEngine.discover(db, actor="api")


@router.post("/reality/evidence", summary="Attach evidence to a claim")
def reality_evidence(claim: str, source_id: int = 0, url: str = "",
                     snippet: str = "", db: Session = Depends(get_db)):
    from app.modules.reality.engine import EvidenceCollector
    return {"id": EvidenceCollector.collect(db, claim, source_id, url, snippet,
                                            actor="api").id}


@router.get("/executive/reality-decision", summary="Reality-first decision")
def reality_decision(question: str, db: Session = Depends(get_db)):
    from app.modules.executive.engine import ExecutiveAgent
    return ExecutiveAgent.decide_reality_first(db, question, actor="api")


class SourceIn(BaseModel):
    name: str
    kind: str
    url: str = ""
    official: bool = False


@router.post("/sources", summary="Register source")
def src_add(payload: SourceIn, db: Session = Depends(get_db)):
    from app.modules.source_intelligence.engine import register_source
    return {"id": register_source(db, actor="api", **payload.model_dump()).id}


@router.get("/sources", summary="Source recommendations")
def src_list(kind: str | None = None, db: Session = Depends(get_db)):
    from app.modules.source_intelligence.engine import recommend_sources
    return {"sources": recommend_sources(db, kind)}


@router.post("/sources/{sid}/score", summary="Score source trust")
def src_score(sid: int, trust: float = 0.0, freshness: float = 0.0,
              authority: float = 0.0, reliability: float = 0.0,
              db: Session = Depends(get_db)):
    from app.modules.reality.engine import SourceTrustEngine
    return {"id": SourceTrustEngine.score(db, sid, trust, freshness, authority,
                                          reliability, actor="api").id}


class AssetIn(BaseModel):
    title: str
    kind: str
    ref_url: str = ""
    source_id: int = 0
    rights_status: str = "unknown"
    attribution: str = ""


@router.post("/assets", summary="Track media asset (reference only)")
def asset_add(payload: AssetIn, db: Session = Depends(get_db)):
    from app.modules.media_acquisition.engine import track_asset
    return {"id": track_asset(db, actor="api", **payload.model_dump()).id}


@router.get("/assets", summary="Media Asset Reports")
def asset_list(db: Session = Depends(get_db)):
    from app.modules.media_acquisition.engine import asset_report
    return {"assets": asset_report(db)}


@router.post("/assets/{aid}/rights", summary="Set rights metadata")
def rights_set(aid: int, license: str = "unknown", owner: str = "",
               db: Session = Depends(get_db)):
    from app.modules.rights.engine import set_rights
    return {"id": set_rights(db, aid, license=license, owner=owner, actor="api").id}


@router.get("/assets/{aid}/rights", summary="Rights status of an asset")
def rights_get(aid: int, db: Session = Depends(get_db)):
    from app.modules.rights.engine import asset_rights
    return asset_rights(db, aid)


@router.post("/verify", summary="Verify a claim")
def verify(subject: str, category: str = "claim", evidence_count: int = 0,
           trusted_hits: int = 0, disputes: int = 0, db: Session = Depends(get_db)):
    from app.modules.verification.engine import verify_claim
    return verify_claim(db, subject, category, "api", evidence_count,
                        trusted_hits, disputes)


@router.get("/verify", summary="Verification Center log")
def verify_log(db: Session = Depends(get_db)):
    from app.modules.verification.engine import verification_log
    return {"verifications": verification_log(db)}


class ArtistIn(BaseModel):
    artist: str
    label: str = ""
    genre: str = ""
    momentum: float = 0.0


@router.post("/artists", summary="Upsert artist intelligence")
def artist_up(payload: ArtistIn, db: Session = Depends(get_db)):
    from app.modules.artist_intelligence.engine import upsert_profile
    return {"id": upsert_profile(db, actor="api", **payload.model_dump()).id}


@router.get("/artists", summary="Artist Intelligence Center")
def artist_list(db: Session = Depends(get_db)):
    from app.modules.artist_intelligence.engine import top_artists
    return {"artists": top_artists(db)}


class LabelIn(BaseModel):
    label: str
    kind: str = "independent"
    activity: float = 0.0


@router.post("/labels", summary="Upsert label intelligence")
def label_up(payload: LabelIn, db: Session = Depends(get_db)):
    from app.modules.label_intelligence.engine import upsert_label
    return {"id": upsert_label(db, actor="api", **payload.model_dump()).id}


@router.get("/labels", summary="Label Intelligence Center")
def label_list(db: Session = Depends(get_db)):
    from app.modules.label_intelligence.engine import active_labels
    return {"labels": active_labels(db)}


class NewsIn(BaseModel):
    kind: str
    title: str
    body: str = ""
    sources: list = []


@router.post("/newsroom", summary="Publish sourced newsroom report")
def news_add(payload: NewsIn, db: Session = Depends(get_db)):
    from app.modules.newsroom.engine import write_report
    return write_report(db, actor="api", **payload.model_dump())


@router.get("/newsroom", summary="Newsroom Center")
def news_list(db: Session = Depends(get_db)):
    from app.modules.newsroom.engine import reports
    return {"reports": reports(db)}


@router.post("/documentary", summary="Build documentary research project")
def doc_build(subject: str, db: Session = Depends(get_db)):
    from app.modules.documentary.engine import build_project
    return build_project(db, subject, actor="api")


@router.post("/documentary/{pid}/package", summary="Ship documentary to Zoza as package")
def doc_ship(pid: int, db: Session = Depends(get_db)):
    from app.modules.documentary.engine import to_package
    return to_package(db, pid, actor="api")


@router.post("/knowledge/graph", summary="Link knowledge graph nodes")
def graph_link(domain: str, src: str, rel: str, dst: str):
    import app.core.shared  # noqa: F401 — ensures creator-os root on sys.path
    from shared.knowledge.graph import link
    return link(domain, src, rel, dst)


@router.get("/knowledge/graph", summary="Knowledge graph neighbors")
def graph_view(domain: str, node: str):
    import app.core.shared  # noqa: F401
    from shared.knowledge.graph import neighbors, graph_stats
    return {"neighbors": neighbors(domain, node), "stats": graph_stats()}
