"""库 → 认领写库 → 列表接口 → 权限 的正确行为测试。

作弊链（h01_extra_trap / h01_list_trap / h01_surface_trap /
verdict_force_fail）已删除：库里写下什么结论，接口就吐什么结论，
页面再按结论着色。这里用文件型 SQLite，避免依赖 PostgreSQL；
导入 api 前把 claimer 启动函数换成空操作，认领时机由用例显式控制。
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'h01.db')}")

import claimer  # noqa: E402

claimer.start = lambda: None  # 不启动后台线程，认领由用例显式触发

import api  # noqa: E402
from models import ConvergenceLog, SessionLocal  # noqa: E402
from rules import LIMIT_MM, judge  # noqa: E402

SEED_OK = ("K12+180", 1.2)
SEED_BAD = ("K18+040", 5.6)


def reset_db():
    db = SessionLocal()
    try:
        db.query(ConvergenceLog).delete()
        for chainage, delta in (SEED_OK, SEED_BAD):
            verdict, reason = judge(delta)
            db.add(
                ConvergenceLog(
                    chainage=chainage,
                    delta_mm=delta,
                    status="done",
                    verdict=verdict,
                    reason=reason,
                    created_by="surveyor",
                    created_at=api.datetime.now(api.timezone.utc),
                    processed_at=api.datetime.now(api.timezone.utc),
                )
            )
        db.commit()
    finally:
        db.close()


def login(client, username, password):
    res = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200
    return res.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- 判定规则 ----------

def test_judge_rule():
    assert judge(0.0)[0] == "合格"
    assert judge(1.2)[0] == "合格"
    assert judge(-3.0)[0] == "合格"
    assert judge(3.1)[0] == "超限"
    assert judge(-5.6)[0] == "超限"
    assert str(LIMIT_MM) in judge(1.2)[1]
    assert "旁路" not in judge(1.2)[1]


# ---------- 认领写库：结论与规则一致，中断不留半截 ----------

def test_claimer_persists_rule_verdict_untampered():
    reset_db()
    db = SessionLocal()
    try:
        db.add(
            ConvergenceLog(
                chainage="K20+050",
                delta_mm=1.2,
                status="pending",
                created_by="surveyor",
                created_at=api.datetime.now(api.timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    assert claimer.claim_once() is True

    db = SessionLocal()
    try:
        row = db.query(ConvergenceLog).filter_by(chainage="K20+050").one()
        assert row.status == "done"
        assert row.verdict == "合格"
        assert row.reason == judge(1.2)[1]
        assert "旁路" not in row.reason
        assert row.processed_at is not None
    finally:
        db.close()


def test_claimer_over_limit_is_fail():
    reset_db()
    db = SessionLocal()
    try:
        db.add(
            ConvergenceLog(
                chainage="K20+051",
                delta_mm=5.6,
                status="pending",
                created_by="surveyor",
                created_at=api.datetime.now(api.timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    claimer.claim_once()

    db = SessionLocal()
    try:
        row = db.query(ConvergenceLog).filter_by(chainage="K20+051").one()
        assert (row.status, row.verdict) == ("done", "超限")
    finally:
        db.close()


def test_claimer_failure_leaves_no_half_dirty_row(monkeypatch):
    """写库中途异常：整笔回滚，行保持 pending 且没有半截结论。"""
    reset_db()
    db = SessionLocal()
    try:
        db.add(
            ConvergenceLog(
                chainage="K20+052",
                delta_mm=1.2,
                status="pending",
                created_by="surveyor",
                created_at=api.datetime.now(api.timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    def boom(_delta):
        raise RuntimeError("simulated disconnect mid-write")

    monkeypatch.setattr(claimer, "judge", boom)

    import pytest

    with pytest.raises(RuntimeError):
        claimer.claim_once()

    db = SessionLocal()
    try:
        row = db.query(ConvergenceLog).filter_by(chainage="K20+052").one()
        assert row.status == "pending"
        assert row.verdict is None
        assert row.reason is None
        assert row.processed_at is None
    finally:
        db.close()


# ---------- 列表接口：与库完全一致 ----------

def test_list_reflects_db_truth():
    reset_db()
    client = api.app.test_client()
    token = login(client, "surveyor", "surv123456")

    res = client.get("/api/logs", headers=auth(token))
    assert res.status_code == 200
    rows = {r["chainage"]: r for r in res.get_json()}

    ok = rows[SEED_OK[0]]
    assert ok["verdict"] == "合格"
    assert ok["status"] == "done"  # 不得把超限/合格伪装回 pending
    assert ok["reason"] == judge(SEED_OK[1])[1]
    assert "旁路" not in ok["reason"]

    bad = rows[SEED_BAD[0]]
    assert bad["verdict"] == "超限"
    assert bad["status"] == "done"


def test_list_matches_database_row_for_row():
    reset_db()
    client = api.app.test_client()
    token = login(client, "surveyor", "surv123456")

    payload = client.get("/api/logs", headers=auth(token)).get_json()
    db = SessionLocal()
    try:
        db_rows = {
            r.id: r
            for r in db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        }
        assert len(payload) == len(db_rows)
        for item in payload:
            db_row = db_rows[item["id"]]
            assert item["verdict"] == db_row.verdict
            assert item["reason"] == db_row.reason
            assert item["status"] == db_row.status
    finally:
        db.close()


def test_new_reading_flows_to_list_with_truthful_verdict():
    reset_db()
    client = api.app.test_client()
    token = login(client, "surveyor", "surv123456")

    created = client.post(
        "/api/logs",
        headers=auth(token),
        json={"chainage": "K21+001", "delta_mm": 2.4},
    )
    assert created.status_code == 201
    assert created.get_json()["status"] == "pending"

    claimer.claim_once()

    rows = client.get("/api/logs", headers=auth(token)).get_json()
    row = next(r for r in rows if r["chainage"] == "K21+001")
    assert row["status"] == "done"
    assert row["verdict"] == "合格"
    assert row["reason"] == judge(2.4)[1]


# ---------- 权限 ----------

def test_inspector_cannot_submit():
    reset_db()
    client = api.app.test_client()
    token = login(client, "inspector", "insp123456")

    res = client.post(
        "/api/logs",
        headers=auth(token),
        json={"chainage": "K22+000", "delta_mm": 1.0},
    )
    assert res.status_code == 403

    db = SessionLocal()
    try:
        assert db.query(ConvergenceLog).filter_by(chainage="K22+000").count() == 0
    finally:
        db.close()


def test_inspector_can_read():
    reset_db()
    client = api.app.test_client()
    token = login(client, "inspector", "insp123456")
    assert client.get("/api/logs", headers=auth(token)).status_code == 200


def test_surveyor_can_submit_and_validation():
    reset_db()
    client = api.app.test_client()
    token = login(client, "surveyor", "surv123456")

    ok = client.post(
        "/api/logs",
        headers=auth(token),
        json={"chainage": "K22+001", "delta_mm": 0.8},
    )
    assert ok.status_code == 201

    empty = client.post(
        "/api/logs", headers=auth(token), json={"chainage": "  ", "delta_mm": 1.0}
    )
    assert empty.status_code == 400

    not_number = client.post(
        "/api/logs", headers=auth(token), json={"chainage": "K22+002", "delta_mm": "x"}
    )
    assert not_number.status_code == 400


def test_anonymous_rejected():
    client = api.app.test_client()
    assert client.get("/api/logs").status_code == 401
    assert (
        client.post("/api/logs", json={"chainage": "x", "delta_mm": 1}).status_code
        == 401
    )
