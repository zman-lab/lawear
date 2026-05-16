#!/usr/bin/env python3
"""17896 시험 콘솔 백엔드 — ThreadingHTTPServer + 정적 파일 + API.

launchd com.lawear.examconsole 호출 (포트 17896, 127.0.0.1 바인드).

Step 1 (commit d08b0cd): 정적 + 헬스 + placeholder.
Step 2 (commit 3c6e73e): SQLite 5 테이블 마이그레이션 v1.
Step 3 (commit 1ddb8a7): 17895 → 17896 동기화 (`/api/sync/preview`, `/api/sync`).
Step 4 (commit d3fed1b): 케이스 API (`/api/cases`, `/api/cases/{id}` + .md 파싱).
Step 5 (commit f4155f3): 시안 HTML 이식 + 케이스/동기화 API wire.
Step 6 (commit e2af4e6): Grader (Anthropic API + 7기준 채점 + mock + env 로더).
Step 7 (commit 0207a5c): Attempts API (POST/GET /api/attempts + background 채점 + 폴링).
Step 8 (commit e38294e): Settings API (GET/PUT /api/settings + weights/bias/voice 검증).
Step 9 (commit e38294e): Bookmarks API (POST/DELETE /api/bookmarks/{case_id}).
Step 10 (commit c6acfb4): Reports 집계 API (overall/by-subject/by-case + subjects/cases picker).
Step 11 (본 커밋): STT placeholder (`POST /api/stt` → 501 stt_not_implemented).
                    실제 STT 는 index.html Web Speech API 클라이언트 사이드 wire.

dev-design archive #48 §3-1 endpoint matrix + §3-3 ErrorCode 1:1.
dev-impl-plan #51 Step 3~11 표 1:1.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import attempts as attempts_mod
import bookmarks as bookmarks_mod
import cases as cases_mod
import db as db_mod
import env_loader  # noqa: F401 — side-effect: .env → os.environ 주입 (Step 6)
import grader as grader_mod
import reports as reports_mod
import settings as settings_mod
import syncer as syncer_mod

# .env 자동 로드 (있으면) — ANTHROPIC_API_KEY 등 환경변수 주입
# 시스템 env 가 우선 (override=False) — 부팅 시점 1회.
env_loader.load_env()

# ─── 설정 (env 우선, 하드코딩 금지) ────────────────────────────────
PORT: int = int(os.environ.get("LAWEAR_EXAM_PORT", "17896"))
BIND: str = os.environ.get("LAWEAR_EXAM_BIND", "127.0.0.1")
ROOT: Path = Path(__file__).parent.resolve()
DB_PATH: str = os.environ.get("LAWEAR_EXAM_DB", str(ROOT / "exam.db"))
SERVER_NAME: str = "lawear-examconsole"
SERVER_VERSION: str = "0.9.0-manual-grading"


class ExamHandler(SimpleHTTPRequestHandler):
    """정적 파일 + 헬스 + API 라우팅.

    SimpleHTTPRequestHandler 상속: index.html 등 정적 자산은 자동 서빙.
    do_GET / do_POST 오버라이드해 /api/* 라우팅 우선, 나머지는 부모 위임.
    """

    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"

    # ─── 라우팅 ────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 헬스 체크
        if path == "/api/health":
            self._send_json(200, {
                "status": "ok",
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "phase": "stt-placeholder",
            })
            return

        # 동기화 미리보기
        if path == "/api/sync/preview":
            self._handle_sync_preview()
            return

        # 케이스 단건: /api/cases/{id}
        if path.startswith("/api/cases/"):
            case_id = path[len("/api/cases/"):]
            # trailing slash 제거 + 빈 id 거부
            case_id = case_id.rstrip("/")
            if not case_id or "/" in case_id:
                self._send_error(400, "bad_request", "invalid case_id")
                return
            self._handle_case_get(case_id)
            return

        # 케이스 목록: /api/cases?filter=...
        if path == "/api/cases":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_cases_list(qs)
            return

        # Attempts 단건: /api/attempts/{id}
        if path.startswith("/api/attempts/"):
            tail = path[len("/api/attempts/"):].rstrip("/")
            if not tail or "/" in tail:
                self._send_error(400, "bad_request", "invalid attempt_id")
                return
            try:
                attempt_id = int(tail)
            except ValueError:
                self._send_error(400, "bad_request", f"attempt_id must be int, got {tail!r}")
                return
            self._handle_attempt_get(attempt_id)
            return

        # Attempts 목록: /api/attempts?case_id=...&subject=...&from=...&to=...&limit=...&offset=...
        if path == "/api/attempts":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_attempts_list(qs)
            return

        # Settings: GET /api/settings
        if path == "/api/settings":
            self._handle_settings_get()
            return

        # Bookmarks 리스트 (옵션): GET /api/bookmarks
        if path == "/api/bookmarks":
            self._handle_bookmarks_list()
            return

        # Reports — Step 10
        if path == "/api/reports/overall":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_reports_overall(qs)
            return
        if path == "/api/reports/by-subject":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_reports_by_subject(qs)
            return
        if path == "/api/reports/by-case":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_reports_by_case(qs)
            return
        if path == "/api/reports/subjects":
            self._handle_reports_subjects()
            return
        if path == "/api/reports/cases":
            qs = urllib.parse.parse_qs(parsed.query)
            self._handle_reports_cases(qs)
            return

        # 미구현 API (Step 11+ placeholder)
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Step 11+ API placeholder ({path})",
            )
            return

        # 정적 파일 (index.html 등) — 부모 위임
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 동기화 적용
        if path == "/api/sync":
            self._handle_sync_apply()
            return

        # Attempts 생성: POST /api/attempts
        if path == "/api/attempts":
            self._handle_attempts_post()
            return

        # Bookmarks 추가: POST /api/bookmarks/{case_id}
        if path.startswith("/api/bookmarks/"):
            case_id = path[len("/api/bookmarks/"):].rstrip("/")
            if not case_id or "/" in case_id:
                self._send_error(400, "bad_request", "invalid case_id")
                return
            self._handle_bookmark_add(urllib.parse.unquote(case_id))
            return

        # STT 서버 사이드 (옵션) — dev-design #48 §3-1 optional row
        # 본 단계에서는 클라이언트 Web Speech API 만 사용. 서버 사이드 STT 는 외부 의존성 +
        # 사용자 결정 + 비용 분석 필요 → 후속. 명시적 501 + 안내 메시지.
        if path == "/api/stt":
            self._send_error(
                501,
                "stt_not_implemented",
                "Server-side STT is not implemented. Use the in-browser Web Speech API (Chrome/Edge).",
            )
            return

        # 미구현 POST (Step 12+ placeholder — Step 11 이후 신규 endpoint 추가 시 위로 이동)
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Unknown API endpoint ({path})",
            )
            return

        # 정적 자원에 POST 는 405
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Settings 저장: PUT /api/settings
        if path == "/api/settings":
            self._handle_settings_put()
            return

        # Step 13 — 외부 채점 결과 주입: PUT /api/attempts/{id}/grade
        if path.startswith("/api/attempts/") and path.endswith("/grade"):
            tail = path[len("/api/attempts/"):-len("/grade")].strip("/")
            if not tail or "/" in tail:
                self._send_error(400, "bad_request", "invalid attempt_id in grade injection path")
                return
            try:
                attempt_id = int(tail)
            except ValueError:
                self._send_error(
                    400, "bad_request", f"attempt_id must be int, got {tail!r}"
                )
                return
            self._handle_attempt_grade_put(attempt_id)
            return

        # 미구현 PUT (Step 11+ placeholder)
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Step 11+ API placeholder ({path})",
            )
            return

        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Bookmarks 제거: DELETE /api/bookmarks/{case_id}
        if path.startswith("/api/bookmarks/"):
            case_id = path[len("/api/bookmarks/"):].rstrip("/")
            if not case_id or "/" in case_id:
                self._send_error(400, "bad_request", "invalid case_id")
                return
            self._handle_bookmark_remove(urllib.parse.unquote(case_id))
            return

        # 미구현 DELETE
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Step 11+ API placeholder ({path})",
            )
            return

        self.send_error(405, "Method Not Allowed")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    # ─── API 핸들러 ────────────────────────────────────────────

    def _handle_sync_preview(self) -> None:
        """`GET /api/sync/preview` — diff 만 (DB 변경 X)."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = syncer_mod.sync_preview(conn)
            self._send_json(200, result)
        except syncer_mod.SyncError as e:
            self._send_error(502, "remote_unreachable", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    def _handle_sync_apply(self) -> None:
        """`POST /api/sync` — UPSERT cases + UPDATE attempts.is_stale."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = syncer_mod.sync_apply(conn)
            self._send_json(200, result)
        except syncer_mod.SyncError as e:
            self._send_error(502, "remote_unreachable", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    def _handle_cases_list(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/cases?filter=...&subject=...&category=...&file=...&search=...`."""
        filter_name = (qs.get("filter") or ["all"])[0]
        subject = (qs.get("subject") or [None])[0]
        category = (qs.get("category") or [None])[0]
        file_name = (qs.get("file") or [None])[0]
        search = (qs.get("search") or [None])[0]
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                items = cases_mod.list_cases(
                    conn,
                    filter_name=filter_name,
                    subject=subject,
                    category=category,
                    file_name=file_name,
                    search=search,
                )
            self._send_json(200, {"cases": items, "total": len(items)})
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    def _handle_case_get(self, case_id: str) -> None:
        """`GET /api/cases/{id}` — 메타 + .md 파싱 origin/lv1/lv4."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                case = cases_mod.get_case(conn, case_id)
            self._send_json(200, case)
        except cases_mod.CaseNotFoundError:
            self._send_error(404, "case_not_found", f"case_id={case_id}")
        except cases_mod.CaseFileMissingError as e:
            self._send_error(500, "md_file_missing", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    # ─── Attempts API (Step 7) ──────────────────────────────────

    def _read_json_body(self) -> dict[str, Any]:
        """요청 본문 JSON 파싱. 빈 본문 → {}."""
        length_hdr = self.headers.get("Content-Length", "0")
        try:
            length = int(length_hdr)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length)
        except (OSError, ConnectionError) as e:
            raise ValueError(f"failed to read body: {e}") from e
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"invalid JSON: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("body must be JSON object")
        return data

    def _handle_attempts_post(self) -> None:
        """`POST /api/attempts` — INSERT + background grader 트리거.

        요청: {"case_id": str, "answer_text": str, "started_at"?, "submitted_at"?}
        응답: 200 {"attempt_id": int, "status": "grading", "case_id", "submitted_at"}

        에러:
          400 bad_request    — JSON 파싱 / case_id / answer_text 빈 값
          404 case_not_found — case_id 미존재
          503 api_key_missing— ANTHROPIC_API_KEY 미설정 (Grader 가 mock auto fallback 하므로
                               본 단계는 실제로 503 안 남. 미래 force_real 옵션 대비)
          500 internal_error — 기타
        """
        # 1. JSON 파싱
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error(400, "bad_request", str(e))
            return

        case_id = body.get("case_id")
        answer_text = body.get("answer_text")
        started_at = body.get("started_at")
        submitted_at = body.get("submitted_at")

        if not isinstance(case_id, str) or not case_id.strip():
            self._send_error(400, "bad_request", "case_id is required")
            return
        if not isinstance(answer_text, str) or not answer_text.strip():
            self._send_error(400, "bad_request", "answer_text is required")
            return

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                # Step 13 — settings.grading_mode 동적 로드 (manual / auto 분기).
                grading_mode = settings_mod.load_grading_mode(conn)
                result = attempts_mod.create_attempt(
                    conn,
                    DB_PATH,
                    case_id=case_id,
                    answer_text=answer_text,
                    started_at=started_at if isinstance(started_at, str) else None,
                    submitted_at=submitted_at if isinstance(submitted_at, str) else None,
                    grading_mode=grading_mode,
                )
            self._send_json(200, result)
        except attempts_mod.AttemptValidationError as e:
            self._send_error(400, e.error_code, str(e))
        except cases_mod.CaseNotFoundError:
            self._send_error(404, "case_not_found", f"case_id={case_id}")
        except cases_mod.CaseFileMissingError as e:
            self._send_error(500, "md_file_missing", str(e))
        except grader_mod.GraderApiKeyMissingError as e:
            # 본 시점에는 mock 자동 fallback 되어 도달 안 함. 명시 처리 유지.
            self._send_error(503, e.error_code, str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_attempt_get(self, attempt_id: int) -> None:
        """`GET /api/attempts/{id}` — 단건 폴링.

        응답:
          status='grading'  : {attempt_id, status, case_id, submitted_at, elapsed_sec}
          status='completed': + total/max/pct/grade + eval_notes + criteria[7] + diff_html
          status='failed'   : + error_code + error_message + retryable
        """
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                attempt = attempts_mod.get_attempt(conn, attempt_id)
            self._send_json(200, attempt)
        except attempts_mod.AttemptNotFoundError as e:
            self._send_error(404, "attempt_not_found", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_attempt_grade_put(self, attempt_id: int) -> None:
        """`PUT /api/attempts/{id}/grade` — 외부 채점 결과 주입 (Step 13).

        Claude Code 메인 세션(Opus)이 manual 모드 attempt 를 채점한 결과를 주입.

        요청 본문 (JSON):
          {
            "criteria": [{key, score, weight_applied, comment}] × 7,
            "total_score": float, "max_score": float, "score_pct": float, "grade": str,
            "eval_notes": {strength, caution, missing},
            "diff_segments": [{type, text}]?,
            "model": str?
          }

        에러:
          400 bad_request          — JSON 파싱 / 필수 필드 누락 / 7기준 키 누락
          404 attempt_not_found    — attempt_id 미존재
          409 already_graded       — 이미 status='done'
          500 internal_error       — 기타
        """
        # 1. JSON 본문 파싱
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error(400, "bad_request", str(e))
            return

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = attempts_mod.inject_grade(conn, attempt_id, body)
            self._send_json(200, result)
        except attempts_mod.AttemptNotFoundError as e:
            self._send_error(404, "attempt_not_found", str(e))
        except attempts_mod.AttemptAlreadyGradedError as e:
            self._send_error(409, "already_graded", str(e))
        except attempts_mod.GradeInjectionError as e:
            self._send_error(400, e.error_code, str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_attempts_list(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/attempts?case_id=&subject=&from_date=&to_date=&status=&limit=&offset=`."""
        def _q1(key: str) -> str | None:
            v = qs.get(key)
            if not v:
                return None
            s = (v[0] or "").strip()
            return s or None

        # from/to alias 지원 (사양에 from/to 와 from_date/to_date 둘 다 등장)
        from_date = _q1("from_date") or _q1("from")
        to_date = _q1("to_date") or _q1("to")

        try:
            limit = int((qs.get("limit") or [str(attempts_mod.DEFAULT_LIST_LIMIT)])[0])
        except (TypeError, ValueError):
            limit = attempts_mod.DEFAULT_LIST_LIMIT
        try:
            offset = int((qs.get("offset") or ["0"])[0])
        except (TypeError, ValueError):
            offset = 0

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = attempts_mod.list_attempts(
                    conn,
                    case_id=_q1("case_id"),
                    subject=_q1("subject"),
                    from_date=from_date,
                    to_date=to_date,
                    status=_q1("status"),
                    limit=limit,
                    offset=offset,
                )
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    # ─── Settings API (Step 8) ──────────────────────────────────

    def _handle_settings_get(self) -> None:
        """`GET /api/settings` — weights/bias/voice 전체 반환."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                data = settings_mod.load_all(conn)
            self._send_json(200, data)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_settings_put(self) -> None:
        """`PUT /api/settings` — 부분 갱신 + 검증 + 저장 후 전체 반환.

        에러:
          400 bad_request    — JSON 파싱 / bias / voice 검증
          409 weights_invalid— weights 합계≠100 또는 키 누락
          500 internal_error — 기타
        """
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error(400, "bad_request", str(e))
            return

        weights = body.get("weights")
        bias = body.get("bias")
        voice = body.get("voice")
        grading_mode = body.get("grading_mode")  # Step 13 — 'manual' | 'auto'

        # 최소 하나는 제공되어야 함 (옵션 — 빈 PUT 도 허용해 현 상태 반환)
        # dev-design #48 PUT 명세 상 부분 갱신 가능 → 빈 객체는 NOOP.

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                data = settings_mod.save_settings(
                    conn,
                    weights=weights if isinstance(weights, dict) else None,
                    bias=bias if isinstance(bias, dict) else None,
                    voice=voice if isinstance(voice, dict) else None,
                    grading_mode=grading_mode if isinstance(grading_mode, str) else None,
                )
            self._send_json(200, data)
        except settings_mod.SettingsValidationError as e:
            # error_code 별 HTTP status 매핑 (dev-design §3-3)
            if e.error_code == "weights_invalid":
                self._send_error(409, e.error_code, str(e))
            else:
                self._send_error(400, e.error_code, str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    # ─── Bookmarks API (Step 9) ─────────────────────────────────

    def _handle_bookmark_add(self, case_id: str) -> None:
        """`POST /api/bookmarks/{case_id}` — 즐겨찾기 추가."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = bookmarks_mod.toggle_add(conn, case_id)
            self._send_json(200, result)
        except bookmarks_mod.BookmarkCaseNotFoundError as e:
            self._send_error(404, "case_not_found", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_bookmark_remove(self, case_id: str) -> None:
        """`DELETE /api/bookmarks/{case_id}` — 즐겨찾기 해제."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = bookmarks_mod.toggle_remove(conn, case_id)
            self._send_json(200, result)
        except bookmarks_mod.BookmarkCaseNotFoundError as e:
            self._send_error(404, "case_not_found", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_bookmarks_list(self) -> None:
        """`GET /api/bookmarks` (옵션) — 즐겨찾기 case_id 리스트."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                data = bookmarks_mod.list_bookmarks(conn)
            self._send_json(200, data)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    # ─── Reports API (Step 10) ─────────────────────────────────

    def _get_stale_threshold_days(self, conn: Any) -> int:
        """settings.bias.stale_threshold_days 로드 (DB / 기본값)."""
        try:
            data = settings_mod.load_all(conn)
            bias = data.get("bias") or {}
            val = bias.get("stale_threshold_days")
            if isinstance(val, int) and val > 0:
                return int(val)
            # 'stale_threshold' alias (마이그 v1 초기 row 키 호환)
            val2 = bias.get("stale_threshold")
            if isinstance(val2, int) and val2 > 0:
                return int(val2)
        except Exception as e:  # noqa: BLE001
            print(
                f"[{SERVER_NAME}] _get_stale_threshold_days: {e} — using default 14",
                file=sys.stderr,
            )
        return reports_mod.DEFAULT_STALE_THRESHOLD_DAYS

    def _handle_reports_overall(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/reports/overall` — KPI 4 + trend + recent."""
        # 옵션 쿼리 파라미터: window_days, trend_limit, trend_days, recent_limit
        def _q_int(key: str, default: int) -> int:
            v = qs.get(key)
            if not v:
                return default
            try:
                return max(1, int(v[0]))
            except (TypeError, ValueError):
                return default

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                stale_days = self._get_stale_threshold_days(conn)
                result = reports_mod.overall(
                    conn,
                    window_days=_q_int("window_days", reports_mod.DEFAULT_WINDOW_DAYS),
                    trend_limit=_q_int("trend_limit", reports_mod.DEFAULT_TREND_LIMIT),
                    trend_days=_q_int("trend_days", reports_mod.DEFAULT_TREND_DAYS),
                    recent_limit=_q_int("recent_limit", reports_mod.DEFAULT_RECENT_LIMIT),
                    stale_threshold_days=stale_days,
                )
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_reports_by_subject(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/reports/by-subject?subject=…` — 단일 과목 + 비교 + 케이스 리스트."""
        subj_list = qs.get("subject") or []
        subject = (subj_list[0] if subj_list else "").strip()
        if not subject:
            self._send_error(400, "bad_request", "subject is required")
            return

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                stale_days = self._get_stale_threshold_days(conn)
                result = reports_mod.by_subject(
                    conn, subject, stale_threshold_days=stale_days
                )
            # subject_exists=False 라도 200 + empty:true (UI 가 "no data" 처리)
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_reports_by_case(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/reports/by-case?case_id=…` — 시도별 + 기준 평균 + 히스토리."""
        cid_list = qs.get("case_id") or []
        case_id = (cid_list[0] if cid_list else "").strip()
        if not case_id:
            self._send_error(400, "bad_request", "case_id is required")
            return

        def _q_int(key: str, default: int) -> int:
            v = qs.get(key)
            if not v:
                return default
            try:
                return max(1, int(v[0]))
            except (TypeError, ValueError):
                return default

        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = reports_mod.by_case(
                    conn,
                    case_id,
                    persistent_threshold=_q_int(
                        "persistent_threshold",
                        reports_mod.DEFAULT_PERSISTENT_THRESHOLD,
                    ),
                )
            # case_exists=False 도 200 + empty:true (UI 가 "no data" 처리)
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_reports_subjects(self) -> None:
        """`GET /api/reports/subjects` — 과목 필터 탭용."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = reports_mod.list_subjects(conn)
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    def _handle_reports_cases(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/reports/cases?subject=…` — By Case 셀렉터용."""
        subj_list = qs.get("subject") or []
        subject = (subj_list[0].strip() if subj_list else None) or None
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = reports_mod.list_cases_for_picker(conn, subject=subject)
            self._send_json(200, result)
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", f"{type(e).__name__}: {e}")

    # ─── CORS / 캐시 헤더 ───────────────────────────────────────
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    # ─── 로그 (17895 server.py 패턴) ─────────────────────────────
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        sys.stderr.write(
            f"[{self.log_date_time_string()}] [{SERVER_NAME}] {format % args}\n"
        )

    # ─── 헬퍼 ─────────────────────────────────────────────────
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, error_code: str, message: str) -> None:
        """dev-design #48 §3-3 ErrorCode 형식."""
        self._send_json(status, {
            "error_code": error_code,
            "message": message,
            "path": self.path,
        })


def main() -> int:
    os.chdir(ROOT)
    # DB 초기화 (멱등 — 매 시작 시 user_version 체크 후 v2 까지 적용)
    db_mod.init_db(DB_PATH)

    # 잔존 'grading' row 마킹 (Q24 A — 이전 부팅 시 죽은 채점 thread 흔적)
    try:
        with db_mod.get_conn(DB_PATH) as conn:
            attempts_mod.mark_orphan_grading(conn)
    except Exception as e:  # noqa: BLE001
        print(f"[{SERVER_NAME}] mark_orphan_grading skipped: {e}", file=sys.stderr)

    # ThreadingHTTPServer (dev-design #48 D-2 / archive #51 §5-2)
    httpd = ThreadingHTTPServer((BIND, PORT), ExamHandler)
    httpd.allow_reuse_address = True
    print(
        f"[{SERVER_NAME}] Serving {ROOT} (db={DB_PATH}) at http://{BIND}:{PORT}",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"[{SERVER_NAME}] shutdown via SIGINT", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
